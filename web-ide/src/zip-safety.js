import { normalizeProjectPath, MAX_FILE_BYTES } from "./storage.js";

const EOCD_SIGNATURE = 0x06054b50;
const CENTRAL_SIGNATURE = 0x02014b50;
const LOCAL_SIGNATURE = 0x04034b50;
const MAX_ARCHIVE_ENTRIES = 300;
const MAX_TOTAL_UNCOMPRESSED = 12 * 1024 * 1024;
const MAX_ARCHIVE_BYTES = 10 * 1024 * 1024;
const FORBIDDEN_COMPONENTS = new Set([".git", ".venv", "venv", "node_modules", "__pycache__"]);

function readU16(view, offset) {
  if (offset < 0 || offset + 2 > view.byteLength) throw new Error("أرشيف ZIP تالف أو مبتور.");
  return view.getUint16(offset, true);
}
function readU32(view, offset) {
  if (offset < 0 || offset + 4 > view.byteLength) throw new Error("أرشيف ZIP تالف أو مبتور.");
  return view.getUint32(offset, true);
}

export function inspectZipArchive(input) {
  const bytes = input instanceof Uint8Array ? input : new Uint8Array(input);
  if (bytes.byteLength < 22) throw new Error("ملف ZIP غير صالح.");
  if (bytes.byteLength > MAX_ARCHIVE_BYTES) throw new Error("حجم ZIP يتجاوز 10 MB.");

  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const searchStart = Math.max(0, bytes.byteLength - 22 - 65535);
  let eocd = -1;
  for (let offset = bytes.byteLength - 22; offset >= searchStart; offset -= 1) {
    if (readU32(view, offset) === EOCD_SIGNATURE) {
      eocd = offset;
      break;
    }
  }
  if (eocd < 0) throw new Error("لم يتم العثور على نهاية دليل ZIP.");

  const diskNumber = readU16(view, eocd + 4);
  const centralDisk = readU16(view, eocd + 6);
  const entriesOnDisk = readU16(view, eocd + 8);
  const entryCount = readU16(view, eocd + 10);
  const centralSize = readU32(view, eocd + 12);
  const centralOffset = readU32(view, eocd + 16);
  const commentLength = readU16(view, eocd + 20);
  if (eocd + 22 + commentLength !== bytes.byteLength) {
    throw new Error("بنية ZIP تحتوي على بيانات زائدة أو تعليق غير مكتمل.");
  }
  if (diskNumber !== 0 || centralDisk !== 0 || entriesOnDisk !== entryCount) {
    throw new Error("أرشيف ZIP متعدد الأقراص غير مدعوم.");
  }
  if (
    entryCount === 0xffff ||
    centralSize === 0xffffffff ||
    centralOffset === 0xffffffff
  ) {
    throw new Error("أرشيف ZIP64 غير مدعوم حالياً.");
  }
  if (entryCount > MAX_ARCHIVE_ENTRIES) {
    throw new Error("عدد عناصر ZIP يتجاوز 300.");
  }
  const centralEnd = centralOffset + centralSize;
  if (centralOffset < 0 || centralEnd !== eocd || centralEnd > bytes.byteLength) {
    throw new Error("دليل ZIP المركزي غير صالح.");
  }

  const decoder = new TextDecoder("utf-8", { fatal: true });
  const entries = [];
  const names = new Set();
  let totalUncompressed = 0;
  let cursor = centralOffset;

  for (let index = 0; index < entryCount; index += 1) {
    if (readU32(view, cursor) !== CENTRAL_SIGNATURE) {
      throw new Error("سجل ملف غير صالح داخل ZIP.");
    }
    const madeBy = readU16(view, cursor + 4);
    const flags = readU16(view, cursor + 8);
    const compressionMethod = readU16(view, cursor + 10);
    const compressedSize = readU32(view, cursor + 20);
    const uncompressedSize = readU32(view, cursor + 24);
    const nameLength = readU16(view, cursor + 28);
    const extraLength = readU16(view, cursor + 30);
    const entryCommentLength = readU16(view, cursor + 32);
    const startDisk = readU16(view, cursor + 34);
    const externalAttributes = readU32(view, cursor + 38);
    const localOffset = readU32(view, cursor + 42);
    const recordEnd = cursor + 46 + nameLength + extraLength + entryCommentLength;

    if (recordEnd > centralEnd || !nameLength) {
      throw new Error("اسم ملف أو سجل ZIP غير مكتمل.");
    }
    if (startDisk !== 0 || (flags & 0x0001)) {
      throw new Error("ملفات ZIP المشفرة أو متعددة الأقراص غير مدعومة.");
    }
    if (compressionMethod !== 0 && compressionMethod !== 8) {
      throw new Error("طريقة ضغط ZIP غير مدعومة.");
    }
    if ([compressedSize, uncompressedSize, localOffset].includes(0xffffffff)) {
      throw new Error("مدخل ZIP64 غير مدعوم.");
    }

    const nameBytes = bytes.subarray(cursor + 46, cursor + 46 + nameLength);
    let rawName;
    try {
      if (!(flags & 0x0800) && nameBytes.some((value) => value > 0x7f)) {
        throw new Error("أسماء الملفات غير UTF-8 غير مدعومة.");
      }
      rawName = decoder.decode(nameBytes);
    } catch {
      throw new Error("تعذر قراءة اسم ملف داخل ZIP.");
    }

    const isDirectory = rawName.endsWith("/");
    const withoutSlash = isDirectory ? rawName.slice(0, -1) : rawName;
    const safePath = normalizeProjectPath(withoutSlash);
    const components = safePath.split("/");
    if (components.some((part) => FORBIDDEN_COMPONENTS.has(part.toLowerCase()))) {
      throw new Error("يحتوي الأرشيف على مجلد نظام أو أدوات غير مسموح باستيرادها: " + safePath);
    }
    if (names.has(safePath)) throw new Error("الأرشيف يحتوي على اسم ملف مكرر: " + safePath);
    names.add(safePath);

    const creatorPlatform = madeBy >>> 8;
    const unixMode = externalAttributes >>> 16;
    if (creatorPlatform === 3 && (unixMode & 0o170000) === 0o120000) {
      throw new Error("روابط الملفات الرمزية غير مسموحة داخل ZIP.");
    }
    if (isDirectory && uncompressedSize !== 0) {
      throw new Error("مدخل مجلد ZIP يحتوي على بيانات غير متوقعة.");
    }
    if (!isDirectory) {
      if (uncompressedSize > MAX_FILE_BYTES) {
        throw new Error("حجم الملف يتجاوز 512 KB: " + safePath);
      }
      totalUncompressed += uncompressedSize;
      if (totalUncompressed > MAX_TOTAL_UNCOMPRESSED) {
        throw new Error("حجم الملفات بعد فك الضغط يتجاوز 12 MB.");
      }
    }

    if (readU32(view, localOffset) !== LOCAL_SIGNATURE) {
      throw new Error("رأس ملف ZIP المحلي غير صالح: " + safePath);
    }
    const localNameLength = readU16(view, localOffset + 26);
    const localExtraLength = readU16(view, localOffset + 28);
    const dataOffset = localOffset + 30 + localNameLength + localExtraLength;
    if (dataOffset + compressedSize > centralOffset) {
      throw new Error("حدود بيانات ZIP غير صالحة: " + safePath);
    }

    if (!safePath.startsWith("__MACOSX/") && safePath !== "__MACOSX") {
      entries.push({ path: safePath, isDirectory, compressedSize, uncompressedSize });
    }
    cursor = recordEnd;
  }

  if (cursor !== centralEnd) throw new Error("دليل ZIP يحتوي على بيانات غير مفهومة.");
  return entries;
}