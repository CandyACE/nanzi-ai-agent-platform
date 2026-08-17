import assert from 'node:assert/strict';
import {
  linkifyGeneratedFileUrls,
  normalizeGeneratedFileHref,
  resolveGeneratedFileHref,
} from '../src/utils/generatedFileUrl.ts';

assert.equal(
  normalizeGeneratedFileHref(
    'http://yovole.com/api/v1/chat/generated-files/0123456789abcdef0123456789abcdef?token=abc#download',
  ),
  '/api/v1/chat/generated-files/0123456789abcdef0123456789abcdef?token=abc#download',
);

assert.equal(
  normalizeGeneratedFileHref('https://example.com/report'),
  'https://example.com/report',
);

const relativeGeneratedFileUrl = '/api/v1/chat/generated-files/0123456789abcdef0123456789abcdef?token=abc_123';
const pageUrl = 'http://localhost:8001/dashboard/chat';
assert.equal(
  resolveGeneratedFileHref(relativeGeneratedFileUrl, pageUrl),
  'http://localhost:8001/api/v1/chat/generated-files/0123456789abcdef0123456789abcdef?token=abc_123',
);

const linked = linkifyGeneratedFileUrls(`下载链接：${relativeGeneratedFileUrl}`, pageUrl);
assert.match(linked, /<a [^>]*href="http:\/\/localhost:8001\/api\/v1\/chat\/generated-files\/0123456789abcdef0123456789abcdef\?token=abc_123"/);
assert.match(linked, /http:\/\/localhost:8001\/api\/v1\/chat\/generated-files\/0123456789abcdef0123456789abcdef\?token=abc_123<\/a>/);
