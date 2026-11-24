export function isPythonSourcePath(path) {
  return typeof path === "string" && /\.pyw?$/i.test(path);
}

export function suggestedDuplicatePath(path) {
  if (typeof path !== "string" || !path) return "";
  return path.replace(/(\.[^./]+)?$/, "_copy$1");
}
