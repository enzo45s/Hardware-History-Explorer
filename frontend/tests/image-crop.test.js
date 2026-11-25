import test from 'node:test';
import assert from 'node:assert/strict';
import { imageCrop } from '../src/image-crop.js';

test('a bounded viewport preserves the exact original image URL', () => {
  assert.deepEqual(imageCrop('https://example.org/catalogue.jpg#hhe-crop=1000,1400,200,300,500,450'), {
    original: 'https://example.org/catalogue.jpg', width: 1000, height: 1400, viewBox: '200 300 500 450'
  });
  assert.equal(imageCrop('https://example.org/photo.jpg'), null);
  assert.equal(imageCrop('/media/local.jpg#hhe-crop=100,100,0,0,100,100').original, '/media/local.jpg');
});

test('invalid geometry and executable URLs cannot create an SVG image', () => {
  for (const geometry of ['100,100,50,50,60,60', '100,100,0,0,0,50', '100,100,-1,0,50,50',
    '100,100,0,0,NaN,50', '100,100,0,0,Infinity,50', '100,100,0,0,50',
    '100,100,0,0,50,50,10', '100001,100,0,0,50,50', '100,100,0,0,50,50&x=1']) {
    assert.equal(imageCrop('https://example.org/a.jpg#hhe-crop=' + geometry), null, geometry);
  }
  for (const url of ['javascript:alert(1)', 'data:image/svg+xml;base64,abc', '//evil.example/a.jpg', 'file:///etc/passwd']) {
    assert.equal(imageCrop(url + '#hhe-crop=100,100,0,0,50,50'), null);
  }
});
