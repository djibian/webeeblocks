#include "file_broker.hpp"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdio>
#include <regex>
#include <sstream>
#include <utility>
#include <vector>

namespace {
constexpr const char *kPrefix = "WEBEEBLOCKS_FILE_BROKER_V1";
constexpr char kBase64Alphabet[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

bool hasBrokerPrefix(const char *message) {
  if (!message)
    return false;
  const std::string prefix = std::string(kPrefix) + " ";
  return std::string(message).compare(0, prefix.size(), prefix) == 0;
}

bool safeToken(const std::string &value) {
  static const std::regex safe("^[A-Za-z0-9_-]{1,128}$");
  return std::regex_match(value, safe);
}

std::string safeCode(const std::string &value) {
  static const std::regex safe("^[A-Z][A-Z0-9_]{0,63}$");
  return std::regex_match(value, safe) ? value : "IO_ERROR";
}

std::string safeProviderName(const std::string &value) {
  static const std::regex safe("^[a-z0-9-]{1,48}$");
  return std::regex_match(value, safe) ? value : "invalid-provider";
}

bool safeSuggestedName(const std::string &value) {
  if (value.empty() || value.size() > 255 || value == "." || value == "..")
    return false;
  return value.find('/') == std::string::npos && value.find('\\') == std::string::npos &&
         value.find('\0') == std::string::npos;
}

std::string base64Encode(const std::string &input) {
  std::string output;
  output.reserve(((input.size() + 2) / 3) * 4);
  for (std::size_t i = 0; i < input.size(); i += 3) {
    const unsigned a = static_cast<unsigned char>(input[i]);
    const unsigned b = i + 1 < input.size() ? static_cast<unsigned char>(input[i + 1]) : 0;
    const unsigned c = i + 2 < input.size() ? static_cast<unsigned char>(input[i + 2]) : 0;
    const unsigned value = (a << 16) | (b << 8) | c;
    output.push_back(kBase64Alphabet[(value >> 18) & 0x3f]);
    output.push_back(kBase64Alphabet[(value >> 12) & 0x3f]);
    output.push_back(i + 1 < input.size() ? kBase64Alphabet[(value >> 6) & 0x3f] : '=');
    output.push_back(i + 2 < input.size() ? kBase64Alphabet[value & 0x3f] : '=');
  }
  return output;
}

int base64Value(char c) {
  if (c >= 'A' && c <= 'Z') return c - 'A';
  if (c >= 'a' && c <= 'z') return c - 'a' + 26;
  if (c >= '0' && c <= '9') return c - '0' + 52;
  if (c == '+') return 62;
  if (c == '/') return 63;
  return -1;
}

bool base64Decode(const std::string &input, std::string *output) {
  if (!output || input.size() % 4 != 0)
    return false;
  output->clear();
  output->reserve((input.size() / 4) * 3);
  for (std::size_t i = 0; i < input.size(); i += 4) {
    const bool last = i + 4 == input.size();
    const char c2 = input[i + 2];
    const char c3 = input[i + 3];
    if ((!last && (c2 == '=' || c3 == '=')) || (c2 == '=' && c3 != '='))
      return false;
    const int a = base64Value(input[i]);
    const int b = base64Value(input[i + 1]);
    const int c = c2 == '=' ? 0 : base64Value(c2);
    const int d = c3 == '=' ? 0 : base64Value(c3);
    if (a < 0 || b < 0 || c < 0 || d < 0)
      return false;
    const unsigned value = (static_cast<unsigned>(a) << 18) | (static_cast<unsigned>(b) << 12) |
                           (static_cast<unsigned>(c) << 6) | static_cast<unsigned>(d);
    output->push_back(static_cast<char>((value >> 16) & 0xff));
    if (c2 != '=') output->push_back(static_cast<char>((value >> 8) & 0xff));
    if (c3 != '=') output->push_back(static_cast<char>(value & 0xff));
  }
  return true;
}

std::vector<std::string> split(const std::string &value) {
  std::vector<std::string> parts;
  std::istringstream stream(value);
  std::string part;
  while (stream >> part)
    parts.push_back(part);
  return parts;
}

std::string responsePrefix(int id) {
  return std::string(kPrefix) + " RESPONSE " + std::to_string(id) + " ";
}

std::string operationError(int id, const std::string &code) {
  return responsePrefix(id) + "ERR " + safeCode(code);
}

std::string openResponse(int id, const webeeblocks::OpenFileResult &result) {
  if (result.status == webeeblocks::FileOperationStatus::Cancelled)
    return responsePrefix(id) + "OPEN CANCELLED";
  if (result.status != webeeblocks::FileOperationStatus::Ok)
    return operationError(id, result.errorCode);
  if (!safeToken(result.reference) || result.name.empty() || result.bytes.size() > webeeblocks::FileBroker::kMaxProjectBytes)
    return operationError(id, "INVALID_PROVIDER_RESULT");
  return responsePrefix(id) + "OPEN OK " + result.reference + " " + base64Encode(result.name) + " " + base64Encode(result.bytes);
}

std::string saveResponse(int id, const char *operation, const webeeblocks::SaveFileResult &result) {
  if (result.status == webeeblocks::FileOperationStatus::Cancelled)
    return responsePrefix(id) + operation + " CANCELLED";
  if (result.status != webeeblocks::FileOperationStatus::Ok)
    return operationError(id, result.errorCode);
  if (!safeToken(result.reference) || result.name.empty())
    return operationError(id, "INVALID_PROVIDER_RESULT");
  return responsePrefix(id) + operation + " OK " + result.reference + " " + base64Encode(result.name);
}
}  // namespace

namespace webeeblocks {

FileBroker::FileBroker(std::unique_ptr<FileDialogProvider> provider) : mProvider(std::move(provider)) {}
FileBroker::~FileBroker() = default;

bool FileBroker::handleMessage(const char *message, std::string *response) {
  if (!hasBrokerPrefix(message))
    return false;
  if (!response)
    return true;
  response->clear();
  if (!mProvider)
    return true;

  const std::string text(message);
  const std::string requestPrefix = std::string(kPrefix) + " REQUEST ";
  if (text.compare(0, requestPrefix.size(), requestPrefix) != 0)
    return true;
  const std::string tail = text.substr(requestPrefix.size());
  const std::vector<std::string> parts = split(tail);
  if (parts.size() < 2)
    return true;

  int id = -1;
  try {
    std::size_t consumed = 0;
    id = std::stoi(parts[0], &consumed);
    if (consumed != parts[0].size() || id < 1)
      return true;
  } catch (...) {
    return true;
  }

  const std::string &operation = parts[1];
  if (operation == "CAPABILITIES" && parts.size() == 2) {
    const std::string provider = safeProviderName(mProvider->name());
    *response = responsePrefix(id) +
      "CAPABILITIES {\"protocol\":1,\"provider\":\"" + provider +
      "\",\"providerInjectable\":true,\"operationsReady\":true,\"sameFileSave\":true,\"canonicalExtension\":\".wbb\"}";
    return true;
  }
  if (operation == "OPEN" && parts.size() == 2) {
    *response = openResponse(id, mProvider->open());
    return true;
  }
  if (operation == "SAVE_AS" && parts.size() == 4) {
    std::string name;
    std::string bytes;
    if (!base64Decode(parts[2], &name) || !base64Decode(parts[3], &bytes) || !safeSuggestedName(name)) {
      *response = operationError(id, "INVALID_REQUEST");
      return true;
    }
    if (bytes.size() > kMaxProjectBytes) {
      *response = operationError(id, "PROJECT_TOO_LARGE");
      return true;
    }
    *response = saveResponse(id, "SAVE_AS", mProvider->saveAs(name, bytes));
    return true;
  }
  if (operation == "SAVE" && parts.size() == 4) {
    std::string bytes;
    if (!safeToken(parts[2]) || !base64Decode(parts[3], &bytes)) {
      *response = operationError(id, "INVALID_REQUEST");
      return true;
    }
    if (bytes.size() > kMaxProjectBytes) {
      *response = operationError(id, "PROJECT_TOO_LARGE");
      return true;
    }
    *response = saveResponse(id, "SAVE", mProvider->save(parts[2], bytes));
    return true;
  }

  *response = operationError(id, "INVALID_REQUEST");
  return true;
}

}  // namespace webeeblocks
