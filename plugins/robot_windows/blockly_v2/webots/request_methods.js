// Vendored from Webots R2025a commit c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b.
// Source: resources/web/wwi/request_methods.js (Apache-2.0).
// Local hardening: flag-style and empty query values remain valid inputs.

// Retrieve the given GET value defined by its "variableName"
// if not found, assign it "defaultValue" instead
function getGETQueryValue(variableName, defaultValue) {
  const query = window.location.search.substring(1);
  const vars = query.split('&');
  for (let i = 0; i < vars.length; i++) {
    const separator = vars[i].indexOf('=');
    const key = separator === -1 ? vars[i] : vars[i].substring(0, separator);
    if (key === variableName)
      return separator === -1 ? '' : vars[i].substring(separator + 1);
  }
  return defaultValue;
}

function getGETQueriesMatchingRegularExpression(pattern) {
  const values = {};
  const query = window.location.search.substring(1);
  if (query === '')
    return values;
  const vars = query.split('&');
  const regex = new RegExp(pattern);
  for (let i = 0; i < vars.length; i++) {
    const separator = vars[i].indexOf('=');
    const key = separator === -1 ? vars[i] : vars[i].substring(0, separator);
    const value = separator === -1 ? '' : vars[i].substring(separator + 1);
    if (regex.test(key))
      values[key.toLowerCase()] = value.toLowerCase();
  }
  return values;
}

export {getGETQueryValue, getGETQueriesMatchingRegularExpression};
