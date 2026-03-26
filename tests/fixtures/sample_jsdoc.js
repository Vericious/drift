/**
 * @name greet
 * Greet a user by name.
 * @param {string} name - The user's name
 * @param {number} [age] - Optional age
 * @returns {string} A greeting message
 */
function greet(name, age) {
    return `Hello, ${name}!`;
}

/**
 * @name add
 * Add two numbers together.
 * @param {number} a - First number
 * @param {number} b - Second number
 * @returns {number} The sum
 */
const add = (a, b) => a + b;

/**
 * @name fetchData
 * Fetch data from a remote API.
 * @param {string} url - The endpoint URL
 * @param {object} options - Fetch options
 * @param {string} options.method - HTTP method
 * @param {number} [options.timeout=5000] - Request timeout in ms
 * @returns {Promise<object>} The response data
 * @throws {Error} If the request fails
 * @see https://api.example.com/docs
 */
async function fetchData(url, options) {
    return await fetch(url, options);
}

/**
 * Callback function type.
 * @callback DataCallback
 * @param {string} err - Error message if any
 * @param {object} data - The fetched data
 */

/**
 * @name processItems
 * Process a list of items with a callback.
 * @param {Array} items - Items to process
 * @param {DataCallback} callback - Called with results
 * @returns {void}
 */
function processItems(items, callback) {
    items.forEach(item => callback(null, item));
}

// Function without JSDoc
function noDocFunc(a, b) {
    return a + b;
}

/**
 * @param {string} msg - A message
 */
function partialDoc(msg) {
    return msg;
}

/**
 * @name legacyFunc
 * @param msg A legacy parameter without type
 */
function legacyFunc(msg) {
    return msg;
}

/** @name simpleName */
const simpleArrow = (x) => x * 2;

/**
 * @returns {boolean} True if ready
 */
function isReady() {
    return true;
}

/**
 * @type {function(string): number}
 */
const parseInt = (s) => Number(s);

/**
 * @throws {TypeError} If input is invalid
 */
function validateInput(input) {
    if (!input) throw new TypeError("Invalid");
}

/**
 * @see {@link https://example.com}
 */
function seeLink() {}

/**
 * @see {@link greet}
 */
function seeRef() {}

// TypeScript-style file
/**
 * @name tsFunc
 * @param {string} a - First arg
 * @param {number} b - Second arg
 * @returns {string} Result
 */
export function tsFunc(a: string, b: number): string {
    return a + b;
}

// Class with JSDoc
class Counter {
    /**
     * @name Counter.increment
     * Increment the counter.
     * @returns {number} The new count
     */
    increment() {
        return 42;
    }
}
