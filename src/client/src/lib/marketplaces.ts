// Local country flag assets shared by generic selectors.
export const FLAG_URL = (code: string) => `/flags/${code === "UK" ? "gb" : code.toLowerCase()}.png`;
