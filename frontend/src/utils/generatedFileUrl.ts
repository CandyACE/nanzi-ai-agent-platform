const GENERATED_FILE_PATH_PREFIX = '/api/v1/chat/generated-files/';
const GENERATED_FILE_URL_PATTERN = /(?:https?:\/\/[^\s<>"']+)?\/api\/v1\/chat\/generated-files\/[0-9a-f]{32}\?token=[A-Za-z0-9_-]+(?:#[A-Za-z0-9._~-]+)?/gi;

const defaultPageUrl = () => {
  if (typeof window !== 'undefined' && window.location?.href) {
    return window.location.href;
  }
  return 'http://placeholder.local/';
};

const escapeHtml = (value: string) => value
  .replace(/&/g, '&amp;')
  .replace(/"/g, '&quot;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;');

export const normalizeGeneratedFileHref = (href: string) => {
  try {
    const url = new URL(href, 'http://placeholder.local');
    if (
      (url.protocol === 'http:' || url.protocol === 'https:')
      && url.pathname.startsWith(GENERATED_FILE_PATH_PREFIX)
    ) {
      return `${url.pathname}${url.search}${url.hash}`;
    }
  } catch {
    // Preserve malformed or non-URL values for the existing renderer logic.
  }

  return href;
};

/** 将生成文件地址绑定到当前页面 Host，供消息展示和点击使用。 */
export const resolveGeneratedFileHref = (href: string, pageUrl = defaultPageUrl()) => {
  try {
    const page = new URL(pageUrl);
    const url = new URL(href, page);
    if (!url.pathname.startsWith(GENERATED_FILE_PATH_PREFIX)) {
      return href;
    }
    url.protocol = page.protocol;
    url.host = page.host;
    return url.href;
  } catch {
    return href;
  }
};

/** 将消息中的裸生成文件地址转换为带完整 Host 的可点击链接。 */
export const linkifyGeneratedFileUrls = (text: string, pageUrl = defaultPageUrl()) =>
  text.replace(GENERATED_FILE_URL_PATTERN, (rawUrl) => {
    const href = resolveGeneratedFileHref(rawUrl, pageUrl);
    const escapedHref = escapeHtml(href);
    return `<a href="${escapedHref}" class="generated-file-link">${escapedHref}</a>`;
  });
