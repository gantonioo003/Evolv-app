const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { dirname, join } = require("node:path");
const { runInNewContext } = require("node:vm");
const ts = require("typescript");

const root = dirname(require.resolve("../package.json"));

function loadComponent(file, modules, globals = {}) {
  const { outputText } = ts.transpileModule(
    readFileSync(join(root, "src", file), "utf8"),
    {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        jsx: ts.JsxEmit.ReactJSX,
      },
    },
  );
  const exported = {};
  runInNewContext(outputText, {
    exports: exported,
    require: (name) => (name in modules ? modules[name] : require(name)),
    ...globals,
  });
  return exported;
}

function touchHarness(reducedMotion = false) {
  const states = [];
  const springs = [];
  const values = [];
  let cursor = 0;
  class Value {
    constructor(value) {
      this.value = value;
      values.push(this);
    }
    setValue(value) {
      this.value = value;
    }
    stopAnimation() {}
    interpolate(config) {
      return config;
    }
  }
  const { TouchFeedback } = loadComponent("components/touch-feedback.tsx", {
    react: {
      useState(initial) {
        const slot = cursor++;
        if (!(slot in states))
          states[slot] = typeof initial === "function" ? initial() : initial;
        return [
          states[slot],
          (value) => {
            states[slot] = value;
          },
        ];
      },
    },
    "react-native": {
      Pressable: "Pressable",
      Platform: { OS: "web" },
      StyleSheet: {
        flatten: (style) =>
          Object.assign({}, ...[style].flat(Infinity).filter(Boolean)),
      },
      Animated: {
        Value,
        createAnimatedComponent: (component) => component,
        spring: (_value, options) => ({
          start() {
            springs.push(options);
          },
        }),
      },
    },
    "@/context/motion-context": { useReducedMotion: () => reducedMotion },
  });
  return {
    springs,
    values,
    render(props) {
      cursor = 0;
      return TouchFeedback(props);
    },
  };
}

test("touch feedback preserves commands, accessibility, disabled state and refs", () => {
  const harness = touchHarness();
  const onPress = () => {};
  const ref = { current: null };
  const button = harness.render({
    onPress,
    disabled: true,
    accessibilityLabel: "Salvar",
    accessibilityRole: "button",
    ref,
  });
  assert.equal(button.props.onPress, onPress);
  assert.equal(button.props.disabled, true);
  assert.equal(button.props.accessibilityLabel, "Salvar");
  assert.equal(button.props.ref, ref);
});

test("press and release use a spring and forward the original events", () => {
  const harness = touchHarness();
  const events = [];
  const button = harness.render({
    onPressIn: (event) => events.push(event),
    onPressOut: (event) => events.push(event),
  });
  const down = { type: "down" };
  const up = { type: "up" };
  button.props.onPressIn(down);
  button.props.onPressOut(up);
  assert.deepEqual(events, [down, up]);
  assert.deepEqual(
    harness.springs.map((spring) => spring.toValue),
    [1, 0],
  );
  assert.ok(
    harness.springs.every((spring) => spring.useNativeDriver === false),
  );
});

test("existing pressed styles and render-function children continue to work", () => {
  const harness = touchHarness();
  const children = ({ pressed }) => String(pressed);
  const props = {
    style: ({ pressed }) => ({
      opacity: pressed ? 0.8 : 1,
      transform: [{ rotate: "5deg" }],
    }),
    children,
  };
  const initial = harness.render(props);
  initial.props.onPressIn({});
  const pressed = harness.render(props);
  assert.equal(pressed.props.style[0].opacity, 0.8);
  assert.equal(pressed.props.style[1].transform[0].rotate, "5deg");
  assert.equal(pressed.props.children, children);
  pressed.props.onPressOut({});
  assert.equal(harness.render(props).props.style[0].opacity, 1);
});

test("reduced motion keeps visual pressed states without starting springs", () => {
  const harness = touchHarness(true);
  const props = { style: ({ pressed }) => ({ opacity: pressed ? 0.8 : 1 }) };
  harness.render(props).props.onPressIn({});
  assert.equal(harness.springs.length, 0);
  assert.equal(harness.values[0].value, 0);
  assert.equal(harness.render(props).props.style[0].opacity, 0.8);
});

test("the web motion preference is read, updated live and unsubscribed", () => {
  let reducedMotion;
  let effect;
  let listener;
  let removed = false;
  const media = {
    matches: false,
    addEventListener(_event, callback) {
      listener = callback;
    },
    removeEventListener(_event, callback) {
      removed = callback === listener;
    },
  };
  const { MotionProvider } = loadComponent(
    "context/motion-context.tsx",
    {
      react: {
        createContext: () => ({ Provider: "Provider" }),
        useState: (initial) => {
          reducedMotion = initial;
          return [
            initial,
            (value) => {
              reducedMotion = value;
            },
          ];
        },
        useEffect: (callback) => {
          effect = callback;
        },
      },
      "react-native": { Platform: { OS: "web" } },
    },
    { matchMedia: () => media },
  );
  MotionProvider({ children: null });
  assert.equal(reducedMotion, true);
  const cleanup = effect();
  assert.equal(reducedMotion, false);
  media.matches = true;
  listener();
  assert.equal(reducedMotion, true);
  cleanup();
  assert.equal(removed, true);
});

test("native motion preference ignores a query that resolves after unmount", async () => {
  let effect;
  let resolve;
  let writes = 0;
  let removed = false;
  const query = new Promise((done) => {
    resolve = done;
  });
  const { MotionProvider } = loadComponent("context/motion-context.tsx", {
    react: {
      createContext: () => ({ Provider: "Provider" }),
      useState: (initial) => [
        initial,
        () => {
          writes += 1;
        },
      ],
      useEffect: (callback) => {
        effect = callback;
      },
    },
    "react-native": {
      Platform: { OS: "ios" },
      AccessibilityInfo: {
        isReduceMotionEnabled: () => query,
        addEventListener: () => ({
          remove() {
            removed = true;
          },
        }),
      },
    },
  });
  MotionProvider({ children: null });
  const cleanup = effect();
  cleanup();
  resolve(false);
  await query;
  assert.equal(writes, 0);
  assert.equal(removed, true);
});
