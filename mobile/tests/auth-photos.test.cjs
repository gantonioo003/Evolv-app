const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { dirname, join } = require("node:path");
const { runInNewContext } = require("node:vm");
const ts = require("typescript");

const root = dirname(require.resolve("../package.json"));
const source = readFileSync(join(root, "src/data/auth-photos.ts"), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  },
});
const exported = {};
runInNewContext(outputText, {
  exports: exported,
  require(specifier) {
    const prefix = "@/assets/images/";
    assert.ok(specifier.startsWith(prefix));
    return join(root, "assets/images", specifier.slice(prefix.length));
  },
});
const { authPhotos, nextAuthPhotoIndex } = exported;

test("the approved gallery contains eight distinct, valid JPEG assets", () => {
  assert.equal(authPhotos.length, 8);
  assert.equal(new Set(authPhotos).size, 8);
  authPhotos.forEach((file, index) => {
    assert.equal(
      file,
      join(root, "assets/images", `auth-selected-0${index + 1}.jpg`),
    );
    const image = readFileSync(file);
    assert.equal(image[0], 0xff);
    assert.equal(image[1], 0xd8);
    assert.equal(image[image.length - 2], 0xff);
    assert.equal(image[image.length - 1], 0xd9);
  });
});

test("first opening and invalid saved values start at the first photo", () => {
  for (const saved of [null, "", "-1", "1.5", "NaN", "undefined", "abc"]) {
    assert.equal(nextAuthPhotoIndex(saved), 0);
  }
});

test("every opening advances one photo and the last wraps to the first", () => {
  const sequence = Array.from({ length: 8 }, (_, index) =>
    nextAuthPhotoIndex(String(index)),
  );
  assert.deepEqual(sequence, [1, 2, 3, 4, 5, 6, 7, 0]);
});

test("saved indices from the old ten-photo gallery reset safely", () => {
  for (const saved of ["8", "9", "10", "9007199254740992"]) {
    assert.equal(nextAuthPhotoIndex(saved), 0);
  }
});
