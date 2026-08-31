// Vendored from Webots R2025a commit c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b.
// Source: resources/web/wwi/request_methods.js (Apache-2.0).

// Retrieve the given GET value defined by its "variableName"
// if not found, assign it "defaultValue" instead
function getGETQueryValue(variableName, defaultValue) {
  const query = window.location.search.substring(1);
  const vars = query.split('&');
  for (let i = 0; i < vars.length; i++) {
    var pair = vars[i].split('=');
    if (pair[0] === variableName)
      return pair[1];
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
    var pair = vars[i].split('=');
    if (regex.test(pair[0]))
      values[pair[0].toLowerCase()] = pair[1].toLowerCase();
  }
  return values;
}

export {getGETQueryValue, getGETQueriesMatchingRegularExpression};
