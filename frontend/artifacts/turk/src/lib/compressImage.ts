// ABOUTME: Client-side image compression — downscale + re-encode a screenshot before upload so
// multi-MB phone screenshots become a few hundred KB. Makes uploads fast and robust on slow /
// flaky mobile connections (a 5-8MB PUT over weak signal was dropping mid-transfer). The verified
// badge stays clearly legible at 1600px, and the backend further downscales the copy it sends to
// the LLM, so this does not hurt detection.

// 2400/q92: keeps files small (a few hundred KB) AND preserves enough badge detail for the CV
// template match. 1600/q85 shrank the badge so much that CV missed ~1/3 of real badges, forcing
// genuinely-verified accounts into review. Validated on the labeled set (see verify/classification).
const MAX_DIM = 2400;                 // longest edge after downscale
const QUALITY = 0.92;                 // JPEG quality
const SKIP_UNDER_BYTES = 600 * 1024;  // already small & no downscale needed -> leave as-is

export async function compressImage(file: File): Promise<File> {
  try {
    if (!file.type.startsWith("image/") || file.type === "image/gif") return file; // leave GIFs/non-images

    const bitmap = await createImageBitmap(file);
    const { width, height } = bitmap;
    const longest = Math.max(width, height);
    const scale = longest > MAX_DIM ? MAX_DIM / longest : 1;

    if (scale === 1 && file.size <= SKIP_UNDER_BYTES) {
      bitmap.close?.();
      return file; // small enough already
    }

    const w = Math.max(1, Math.round(width * scale));
    const h = Math.max(1, Math.round(height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      bitmap.close?.();
      return file;
    }
    ctx.drawImage(bitmap, 0, 0, w, h);
    bitmap.close?.();

    const blob: Blob | null = await new Promise((resolve) =>
      canvas.toBlob((b) => resolve(b), "image/jpeg", QUALITY),
    );
    if (!blob || blob.size >= file.size) return file; // no real gain -> keep original

    const name = file.name.replace(/\.[a-z0-9]+$/i, "") + ".jpg";
    return new File([blob], name, { type: "image/jpeg", lastModified: Date.now() });
  } catch {
    return file; // any failure -> upload the original, unchanged
  }
}
