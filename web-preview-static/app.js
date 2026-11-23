const $=id=>document.getElementById(id);
const input=$("project-zip"),zone=$("upload-zone"),fileState=$("file-state"),message=$("preview-message");
function announce(text){message.textContent=text}
$("choose-zip").addEventListener("click",()=>input.click());
input.addEventListener("change",()=>{
 const file=input.files&&input.files[0];
 if(!file){fileState.textContent="لم يتم اختيار ملف بعد";return}
 if(!file.name.toLowerCase().endsWith(".zip")){fileState.textContent="الملف يجب أن يكون ZIP";announce("لم يتم قبول الملف: اختر أرشيف ZIP لمشروع Flet.");input.value="";return}
 if(file.size>12*1024*1024){fileState.textContent="حجم الملف أكبر من 12 MB";announce("حجم الملف يتجاوز الحد الذي تقبله الأداة.");input.value="";return}
 fileState.textContent="تم اختيار: "+file.name+" · "+(file.size/1024/1024).toFixed(2)+" MB";
 announce("تم اختيار الملف محلياً للمعاينة فقط. لم يتم رفعه إلى أي خادم.");
});
["dragenter","dragover"].forEach(type=>zone.addEventListener(type,event=>{event.preventDefault();zone.classList.add("drag")}));
["dragleave","drop"].forEach(type=>zone.addEventListener(type,event=>{event.preventDefault();zone.classList.remove("drag")}));
zone.addEventListener("drop",event=>{
 const file=event.dataTransfer&&event.dataTransfer.files&&event.dataTransfer.files[0];
 if(!file)return;
 if(!file.name.toLowerCase().endsWith(".zip")||file.size>12*1024*1024){announce("اختر ملف ZIP لا يتجاوز 12 MB.");return}
 input.files=event.dataTransfer.files;
 input.dispatchEvent(new Event("change"));
});
$("starter-btn").addEventListener("click",()=>announce("إنشاء القالب متاح داخل تطبيق Flet. هذه الصفحة لا تنشئ ملفات فعلية."));
["connect-btn","repos-btn","new-repo-btn"].forEach(id=>$(id).addEventListener("click",()=>announce("ربط GitHub وإدارة المستودعات غير مفعّلين في معاينة الويب.")));
$("build-btn").addEventListener("click",()=>announce("لم يبدأ أي بناء. استخدم تطبيق Flet APK Studio لرفع المشروع وتشغيل GitHub Actions."));
$("refresh-btn").addEventListener("click",()=>announce("لا توجد عملية بناء مرتبطة بهذه المعاينة. حالة البناء الحقيقية تظهر داخل التطبيق بعد الربط."));
