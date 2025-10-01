/**
 * test_js_edge_cases.js
 * * A set of JavaScript functions and classes using JSDoc to test the esprima-based 
 * analyzer's ability to extract descriptions, parameters (including optional), 
 * return types, and handle various function declaration styles.
 */

// Global constants for testing character set documentation
const ALPHABETS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';
const NUMBERS = '0123456789';

// 1. Class with a constructor and standard method
class UserProfile {
    /**
     * Creates an instance of UserProfile.
     * @param {string} userName The unique name of the user.
     * @param {number} userId The numerical ID of the user.
     */
    constructor(userName, userId) {
        this.name = userName;
        this.id = userId;
    }

    /**
     * Generates a display name combining the user's name and ID.
     * @returns {string} The formatted display name.
     */
    getDisplayName() {
        return `${this.name} (#${this.id})`;
    }
}

// 2. Function assigned to a variable (Function Expression) with minimal JSDoc
/**
 * Calculates the product of two numbers.
 * @param {number} x The first factor.
 * @param {number} y The second factor.
 * @return {number} The result of the multiplication.
 */
const multiply = function(x, y) {
    return x * y;
};

// 3. Arrow Function with destructuring in parameters (Testing range extraction)
/**
 * Processes a configuration object, extracting host and port.
 * @param {object} settings The configuration settings.
 * @param {string} settings.host The network address.
 * @param {number} [settings.port=80] The port number (optional, defaults to 80).
 * @returns {string} A connection string.
 */
const createConnectionString = ({ host, port = 80 }) => {
    return `http://${host}:${port}`;
};

// 4. Function with optional parameter documented using brackets
/**
 * Retrieves an element by its ID.
 * @param {string} elementId The DOM element's ID string.
 * @param {boolean} [shouldCache=false] If true, the element will be stored in a local cache.
 * @returns {HTMLElement|null} The requested HTML element, or null if not found.
 */
function getElement(elementId, shouldCache = false) {
    const element = document.getElementById(elementId);
    if (shouldCache && element) {
        // Cache logic...
    }
    return element;
}

// 5. Async Function testing the @async tag (if supported by parser)
/**
 * Fetches user data asynchronously from a remote endpoint.
 * This is a test for multi-line descriptions and complex return types.
 * * @param {string} url The API endpoint URL.
 * @param {string} [token] The optional authorization token for the request.
 * @returns {Promise<object>} A promise that resolves with the parsed JSON user object.
 * @async
 */
async function fetchUserData(url, token) {
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
    const response = await fetch(url, { headers });
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
}

// 6. Function with parameters listed in code but missing from JSDoc
// The analyzer should still list the parameters from the code signature.
/**
 * This docstring only describes what the function does.
 */
function performSimpleOperation(valueA, valueB, operationType) {
    if (operationType === 'add') {
        return valueA + valueB;
    }
    return valueA - valueB;
}

// 7. JSDoc with intentional formatting error (missing type braces)
/**
 * Logs a message to the console.
 * @param message The message content.
 * @returns nothing
 */
function logMessage(message) {
    console.log(message);
}
