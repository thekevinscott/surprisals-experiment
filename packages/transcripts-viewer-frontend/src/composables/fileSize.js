export const fileSize = bytes => Number.isFinite(bytes) ? bytes < 1024 ? `${bytes} B` : `${Number((bytes / 1024).toFixed(1))} KB` : ''
