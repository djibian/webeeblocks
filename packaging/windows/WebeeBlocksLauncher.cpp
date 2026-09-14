#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <shellapi.h>

#include <algorithm>
#include <atomic>
#include <cctype>
#include <cstdint>
#include <cwctype>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace fs = std::filesystem;

namespace {

std::atomic<bool> g_stop{false};
SOCKET g_listener = INVALID_SOCKET;

std::string read_bytes(const fs::path &path) {
  std::ifstream stream(path, std::ios::binary);
  if (!stream)
    throw std::runtime_error("cannot read " + path.u8string());
  return std::string(std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>());
}

void write_bytes(const fs::path &path, const std::string &data) {
  std::ofstream stream(path, std::ios::binary | std::ios::trunc);
  if (!stream)
    throw std::runtime_error("cannot write " + path.u8string());
  stream.write(data.data(), static_cast<std::streamsize>(data.size()));
  if (!stream)
    throw std::runtime_error("cannot finish writing " + path.u8string());
}

std::wstring widen(const std::string &value) {
  if (value.empty())
    return L"";
  int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
                                  static_cast<int>(value.size()), nullptr, 0);
  if (count <= 0)
    throw std::runtime_error("invalid UTF-8");
  std::wstring result(static_cast<size_t>(count), L'\0');
  MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
                      static_cast<int>(value.size()), result.data(), count);
  return result;
}

std::wstring quote_arg(const std::wstring &arg) {
  std::wstring out = L"\"";
  size_t backslashes = 0;
  for (wchar_t ch : arg) {
    if (ch == L'\\') {
      ++backslashes;
      continue;
    }
    if (ch == L'\"') {
      out.append(backslashes * 2 + 1, L'\\');
      out.push_back(L'\"');
      backslashes = 0;
      continue;
    }
    out.append(backslashes, L'\\');
    backslashes = 0;
    out.push_back(ch);
  }
  out.append(backslashes * 2, L'\\');
  out.push_back(L'\"');
  return out;
}

fs::path executable_dir() {
  std::vector<wchar_t> buffer(32768);
  DWORD count = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
  if (count == 0 || count >= buffer.size())
    throw std::runtime_error("cannot resolve launcher path");
  return fs::path(std::wstring(buffer.data(), count)).parent_path();
}

bool is_inside(const fs::path &root, const fs::path &target) {
  fs::path canonical_root = fs::weakly_canonical(root);
  fs::path canonical_target = fs::weakly_canonical(target);
  auto root_it = canonical_root.begin();
  auto target_it = canonical_target.begin();
  for (; root_it != canonical_root.end(); ++root_it, ++target_it) {
    if (target_it == canonical_target.end())
      return false;
    std::wstring a = root_it->wstring();
    std::wstring b = target_it->wstring();
    std::transform(a.begin(), a.end(), a.begin(), [](wchar_t c) { return static_cast<wchar_t>(std::towlower(c)); });
    std::transform(b.begin(), b.end(), b.begin(), [](wchar_t c) { return static_cast<wchar_t>(std::towlower(c)); });
    if (a != b)
      return false;
  }
  return true;
}

std::string mime_type(const fs::path &path) {
  std::string ext = path.extension().u8string();
  std::transform(ext.begin(), ext.end(), ext.begin(),
                 [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
  if (ext == ".html") return "text/html; charset=utf-8";
  if (ext == ".css") return "text/css; charset=utf-8";
  if (ext == ".js") return "application/javascript; charset=utf-8";
  if (ext == ".json") return "application/json; charset=utf-8";
  if (ext == ".png") return "image/png";
  if (ext == ".jpg" || ext == ".jpeg") return "image/jpeg";
  if (ext == ".svg") return "image/svg+xml";
  if (ext == ".ico") return "image/x-icon";
  return "application/octet-stream";
}

void send_all(SOCKET socket_handle, const char *data, size_t length) {
  while (length > 0) {
    int chunk = send(socket_handle, data, static_cast<int>(std::min<size_t>(length, 1u << 20)), 0);
    if (chunk == SOCKET_ERROR)
      return;
    data += chunk;
    length -= static_cast<size_t>(chunk);
  }
}

void send_reply(SOCKET client, int status, const char *reason,
                const std::string &content_type, const std::string &body) {
  std::ostringstream header;
  header << "HTTP/1.1 " << status << " " << reason << "\r\n"
         << "Content-Type: " << content_type << "\r\n"
         << "Content-Length: " << body.size() << "\r\n"
         << "Cache-Control: no-store, no-cache, must-revalidate\r\n"
         << "Pragma: no-cache\r\n"
         << "Access-Control-Allow-Origin: *\r\n"
         << "Connection: close\r\n\r\n";
  const std::string text = header.str();
  send_all(client, text.data(), text.size());
  send_all(client, body.data(), body.size());
}

std::string percent_decode(const std::string &value) {
  std::string out;
  out.reserve(value.size());
  auto hex = [](char c) -> int {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return 10 + c - 'a';
    if (c >= 'A' && c <= 'F') return 10 + c - 'A';
    return -1;
  };
  for (size_t i = 0; i < value.size(); ++i) {
    if (value[i] == '%' && i + 2 < value.size()) {
      int hi = hex(value[i + 1]);
      int lo = hex(value[i + 2]);
      if (hi >= 0 && lo >= 0) {
        out.push_back(static_cast<char>((hi << 4) | lo));
        i += 2;
        continue;
      }
    }
    out.push_back(value[i]);
  }
  return out;
}

void serve_client(SOCKET client, const fs::path &root) {
  std::string request;
  char buffer[2048];
  while (request.find("\r\n\r\n") == std::string::npos && request.size() < 16384) {
    int got = recv(client, buffer, sizeof(buffer), 0);
    if (got <= 0)
      return;
    request.append(buffer, static_cast<size_t>(got));
  }
  size_t line_end = request.find("\r\n");
  if (line_end == std::string::npos) {
    send_reply(client, 400, "Bad Request", "text/plain; charset=utf-8", "Bad Request");
    return;
  }
  std::istringstream line(request.substr(0, line_end));
  std::string method, uri, version;
  line >> method >> uri >> version;
  if (method != "GET") {
    send_reply(client, 405, "Method Not Allowed", "text/plain; charset=utf-8", "Method Not Allowed");
    return;
  }
  size_t query = uri.find('?');
  std::string raw_path = query == std::string::npos ? uri : uri.substr(0, query);
  if (raw_path.empty() || raw_path[0] != '/') {
    send_reply(client, 404, "Not Found", "text/plain; charset=utf-8", "Not Found");
    return;
  }
  std::string decoded = percent_decode(raw_path.substr(1));
  std::replace(decoded.begin(), decoded.end(), '/', '\\');
  fs::path target = fs::weakly_canonical(root / fs::u8path(decoded));
  if (!is_inside(root, target) || !fs::is_regular_file(target)) {
    send_reply(client, 404, "Not Found", "text/plain; charset=utf-8", "Not Found");
    return;
  }
  send_reply(client, 200, "OK", mime_type(target), read_bytes(target));
}

void server_loop(fs::path root) {
  while (!g_stop.load()) {
    SOCKET client = accept(g_listener, nullptr, nullptr);
    if (client == INVALID_SOCKET)
      break;
    try {
      serve_client(client, root);
    } catch (...) {
      send_reply(client, 500, "Internal Server Error", "text/plain; charset=utf-8",
                 "Internal Server Error");
    }
    shutdown(client, SD_BOTH);
    closesocket(client);
  }
}

struct Server {
  WSADATA wsa{};
  std::thread thread;
  unsigned short port = 0;

  explicit Server(const fs::path &root) {
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0)
      throw std::runtime_error("Winsock initialization failed");
    g_listener = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (g_listener == INVALID_SOCKET) {
      WSACleanup();
      throw std::runtime_error("local server socket creation failed");
    }
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    address.sin_port = 0;
    if (bind(g_listener, reinterpret_cast<sockaddr *>(&address), sizeof(address)) == SOCKET_ERROR ||
        listen(g_listener, SOMAXCONN) == SOCKET_ERROR) {
      closesocket(g_listener);
      g_listener = INVALID_SOCKET;
      WSACleanup();
      throw std::runtime_error("local server bind/listen failed");
    }
    int length = sizeof(address);
    if (getsockname(g_listener, reinterpret_cast<sockaddr *>(&address), &length) == SOCKET_ERROR) {
      closesocket(g_listener);
      g_listener = INVALID_SOCKET;
      WSACleanup();
      throw std::runtime_error("local server port discovery failed");
    }
    port = ntohs(address.sin_port);
    g_stop.store(false);
    thread = std::thread(server_loop, root);
  }

  ~Server() {
    g_stop.store(true);
    if (g_listener != INVALID_SOCKET) {
      shutdown(g_listener, SD_BOTH);
      closesocket(g_listener);
      g_listener = INVALID_SOCKET;
    }
    if (thread.joinable())
      thread.join();
    WSACleanup();
  }

  Server(const Server &) = delete;
  Server &operator=(const Server &) = delete;
};

std::string url_encode_path(std::string value) {
  std::string out;
  static const char *hex = "0123456789ABCDEF";
  for (unsigned char c : value) {
    if (std::isalnum(c) || c == '/' || c == '-' || c == '_' || c == '.' || c == '~') {
      out.push_back(static_cast<char>(c));
    } else {
      out.push_back('%');
      out.push_back(hex[c >> 4]);
      out.push_back(hex[c & 15]);
    }
  }
  return out;
}

std::string rewrite_html(const std::string &html, const fs::path &plugin_root,
                         const fs::path &package_root, unsigned short port) {
  static const std::regex attr(R"((src|href)="([^"]+)")", std::regex::icase);
  static const std::regex scheme(R"(^[A-Za-z][A-Za-z0-9+.-]*:)");
  std::string output;
  size_t cursor = 0;
  size_t count = 0;
  for (std::sregex_iterator it(html.begin(), html.end(), attr), end; it != end; ++it) {
    const std::smatch &match = *it;
    std::string url = match[2].str();
    if (url.empty() || url[0] == '#' || url.rfind("//", 0) == 0 ||
        std::regex_search(url, scheme))
      throw std::runtime_error("unexpected non-local Robot Window dependency: " + url);

    size_t split = url.find_first_of("?#");
    std::string path_part = split == std::string::npos ? url : url.substr(0, split);
    std::string suffix = split == std::string::npos ? "" : url.substr(split);
    fs::path asset = fs::weakly_canonical(plugin_root / fs::u8path(path_part));
    if (!is_inside(package_root, asset) || !fs::is_regular_file(asset))
      throw std::runtime_error("missing Robot Window dependency: " + path_part);
    fs::path relative = fs::relative(asset, package_root);
    std::string relative_url = relative.generic_u8string();

    output.append(html, cursor, static_cast<size_t>(match.position()) - cursor);
    output += match[1].str();
    output += "=\"http://127.0.0.1:" + std::to_string(port) + "/" +
              url_encode_path(relative_url) + suffix + "\"";
    cursor = static_cast<size_t>(match.position() + match.length());
    ++count;
  }
  output.append(html, cursor, std::string::npos);
  if (count < 10)
    throw std::runtime_error("Robot Window dependency set is unexpectedly small");
  size_t head = output.find("<head>");
  if (head != std::string::npos)
    output.insert(head + 6, "<link rel=\"icon\" href=\"data:,\">");
  return output;
}

std::string canonical_window_name(const std::string &world) {
  static const std::regex line(R"((?:^|\r?\n)\s*window\s+"(blockly_v2_[0-9a-f]{16})"\s*(?:\r?\n|$))");
  std::sregex_iterator it(world.begin(), world.end(), line), end;
  if (it == end)
    throw std::runtime_error("packaged world has no content-addressed Robot Window");
  std::string name = (*it)[1].str();
  ++it;
  if (it != end)
    throw std::runtime_error("packaged world has multiple Robot Windows");
  return name;
}

std::string replace_once(const std::string &source, const std::string &from,
                         const std::string &to) {
  size_t first = source.find(from);
  if (first == std::string::npos || source.find(from, first + from.size()) != std::string::npos)
    throw std::runtime_error("expected exactly one session replacement target");
  std::string result = source;
  result.replace(first, from.size(), to);
  return result;
}

std::wstring environment(const wchar_t *name) {
  DWORD count = GetEnvironmentVariableW(name, nullptr, 0);
  if (count == 0)
    return L"";
  std::wstring value(static_cast<size_t>(count), L'\0');
  DWORD written = GetEnvironmentVariableW(name, value.data(), count);
  if (written == 0 || written >= count)
    return L"";
  value.resize(written);
  return value;
}

bool file_exists(const fs::path &path) {
  std::error_code error;
  return fs::is_regular_file(path, error);
}

std::string capture_process(const fs::path &exe, const std::wstring &args) {
  SECURITY_ATTRIBUTES security{sizeof(SECURITY_ATTRIBUTES), nullptr, TRUE};
  HANDLE read_pipe = nullptr, write_pipe = nullptr;
  if (!CreatePipe(&read_pipe, &write_pipe, &security, 0))
    throw std::runtime_error("cannot create version pipe");
  SetHandleInformation(read_pipe, HANDLE_FLAG_INHERIT, 0);

  STARTUPINFOW startup{};
  startup.cb = sizeof(startup);
  startup.dwFlags = STARTF_USESTDHANDLES;
  startup.hStdOutput = write_pipe;
  startup.hStdError = write_pipe;
  startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
  PROCESS_INFORMATION process{};
  std::wstring command = quote_arg(exe.wstring()) + L" " + args;
  std::vector<wchar_t> mutable_command(command.begin(), command.end());
  mutable_command.push_back(L'\0');
  BOOL ok = CreateProcessW(exe.c_str(), mutable_command.data(), nullptr, nullptr, TRUE,
                           CREATE_NO_WINDOW, nullptr, exe.parent_path().c_str(),
                           &startup, &process);
  CloseHandle(write_pipe);
  if (!ok) {
    CloseHandle(read_pipe);
    throw std::runtime_error("cannot execute Webots version probe");
  }

  std::string output;
  char buffer[1024];
  DWORD got = 0;
  while (ReadFile(read_pipe, buffer, sizeof(buffer), &got, nullptr) && got > 0)
    output.append(buffer, static_cast<size_t>(got));
  CloseHandle(read_pipe);
  DWORD wait = WaitForSingleObject(process.hProcess, 10000);
  if (wait == WAIT_TIMEOUT) {
    TerminateProcess(process.hProcess, 1);
    WaitForSingleObject(process.hProcess, 5000);
  }
  DWORD exit_code = 1;
  GetExitCodeProcess(process.hProcess, &exit_code);
  CloseHandle(process.hThread);
  CloseHandle(process.hProcess);
  if (wait == WAIT_TIMEOUT || exit_code != 0)
    throw std::runtime_error("Webots version probe failed");
  return output;
}

struct Webots {
  fs::path gui;
};

Webots find_webots() {
  std::vector<fs::path> homes;
  std::wstring configured = environment(L"WEBOTS_HOME");
  if (!configured.empty())
    homes.emplace_back(configured);
  std::wstring program_files = environment(L"ProgramFiles");
  if (!program_files.empty())
    homes.push_back(fs::path(program_files) / L"Webots");

  for (const fs::path &home : homes) {
    fs::path bin = home / L"msys64" / L"mingw64" / L"bin";
    fs::path console = bin / L"webots.exe";
    fs::path gui = bin / L"webotsw.exe";
    if (!file_exists(console))
      continue;
    std::string version = capture_process(console, L"--version");
    if (version.find("R2025a") == std::string::npos)
      continue;
    return Webots{file_exists(gui) ? gui : console};
  }

  wchar_t found[32768];
  DWORD count = SearchPathW(nullptr, L"webots.exe", nullptr, 32768, found, nullptr);
  if (count > 0 && count < 32768) {
    fs::path console(found);
    std::string version = capture_process(console, L"--version");
    if (version.find("R2025a") != std::string::npos) {
      fs::path gui = console.parent_path() / L"webotsw.exe";
      return Webots{file_exists(gui) ? gui : console};
    }
  }
  throw std::runtime_error("Webots R2025a not found");
}

DWORD launch_webots(const Webots &webots, const fs::path &world, const fs::path &working_dir) {
  std::wstring command = quote_arg(webots.gui.wstring()) + L" --mode=realtime " +
                         quote_arg(world.wstring());
  std::vector<wchar_t> mutable_command(command.begin(), command.end());
  mutable_command.push_back(L'\0');
  STARTUPINFOW startup{};
  startup.cb = sizeof(startup);
  PROCESS_INFORMATION process{};
  if (!CreateProcessW(webots.gui.c_str(), mutable_command.data(), nullptr, nullptr, FALSE, 0,
                      nullptr, working_dir.c_str(), &startup, &process))
    throw std::runtime_error("cannot start Webots");
  CloseHandle(process.hThread);
  WaitForSingleObject(process.hProcess, INFINITE);
  DWORD exit_code = 1;
  GetExitCodeProcess(process.hProcess, &exit_code);
  CloseHandle(process.hProcess);
  return exit_code;
}

void ensure_server_response(unsigned short port, const std::string &relative_path,
                            const std::string &expected_body,
                            const std::string &expected_type) {
  SOCKET socket_handle = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
  if (socket_handle == INVALID_SOCKET)
    throw std::runtime_error("validation socket creation failed");
  sockaddr_in address{};
  address.sin_family = AF_INET;
  address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  address.sin_port = htons(port);
  if (connect(socket_handle, reinterpret_cast<sockaddr *>(&address), sizeof(address)) == SOCKET_ERROR) {
    closesocket(socket_handle);
    throw std::runtime_error("validation connection failed");
  }
  std::string request = "GET /" + relative_path +
                        " HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n";
  send_all(socket_handle, request.data(), request.size());
  std::string response;
  char buffer[4096];
  for (;;) {
    int got = recv(socket_handle, buffer, sizeof(buffer), 0);
    if (got <= 0)
      break;
    response.append(buffer, static_cast<size_t>(got));
  }
  closesocket(socket_handle);
  size_t split = response.find("\r\n\r\n");
  if (split == std::string::npos || response.rfind("HTTP/1.1 200 OK\r\n", 0) != 0 ||
      response.find("Content-Type: " + expected_type + "\r\n") == std::string::npos ||
      response.substr(split + 4) != expected_body)
    throw std::runtime_error("local server validation mismatch");
}

struct SessionFiles {
  fs::path plugin_dir;
  fs::path world;
  ~SessionFiles() {
    std::error_code error;
    if (!world.empty()) fs::remove(world, error);
    if (!plugin_dir.empty()) fs::remove_all(plugin_dir, error);
  }
};

int run(bool validate_only) {
  fs::path package_root = executable_dir();
  fs::path canonical_world = package_root / L"worlds" / L"crazyflie_runtime_v2.wbt";
  if (!file_exists(canonical_world))
    throw std::runtime_error("packaged world is missing");
  std::string world_text = read_bytes(canonical_world);
  if (std::regex_search(world_text, std::regex(R"("(?:https?|webots)://)", std::regex::icase)))
    throw std::runtime_error("packaged world still contains a remote resource");

  std::string canonical_name = canonical_window_name(world_text);
  fs::path canonical_plugin = package_root / L"plugins" / L"robot_windows" / widen(canonical_name);
  fs::path canonical_html = canonical_plugin / widen(canonical_name + ".html");
  if (!file_exists(canonical_html))
    throw std::runtime_error("packaged Robot Window is missing");
  std::string canonical_html_bytes = read_bytes(canonical_html);

  Webots webots = find_webots();
  Server server(package_root);

  DWORD pid = GetCurrentProcessId();
  ULONGLONG tick = GetTickCount64();
  std::ostringstream session_name_stream;
  session_name_stream << "webeeblocks_session_" << std::hex << pid << "_" << tick;
  std::string session_name = session_name_stream.str();

  SessionFiles session;
  session.plugin_dir = package_root / L"plugins" / L"robot_windows" / widen(session_name);
  session.world = package_root / L"worlds" / widen("." + session_name + ".wbt");
  if (fs::exists(session.plugin_dir) || fs::exists(session.world))
    throw std::runtime_error("session path collision");
  fs::create_directory(session.plugin_dir);

  std::string proxied_html =
      rewrite_html(canonical_html_bytes, canonical_plugin, package_root, server.port);
  write_bytes(session.plugin_dir / widen(session_name + ".html"), proxied_html);
  std::string session_world =
      replace_once(world_text, "window \"" + canonical_name + "\"",
                    "window \"" + session_name + "\"");
  write_bytes(session.world, session_world);

  std::string main_css_relative =
      fs::relative(canonical_plugin / L"main.css", package_root).generic_u8string();
  ensure_server_response(server.port, url_encode_path(main_css_relative),
                         read_bytes(canonical_plugin / L"main.css"),
                         "text/css; charset=utf-8");

  if (read_bytes(canonical_html) != canonical_html_bytes ||
      read_bytes(canonical_world) != world_text)
    throw std::runtime_error("canonical release files changed during session preparation");

  if (validate_only)
    return 0;

  DWORD exit_code = launch_webots(webots, session.world, package_root);
  if (exit_code != 0)
    throw std::runtime_error("Webots exited with code " + std::to_string(exit_code));
  return 0;
}

bool has_arg(int argc, wchar_t **argv, const wchar_t *wanted) {
  for (int i = 1; i < argc; ++i)
    if (_wcsicmp(argv[i], wanted) == 0)
      return true;
  return false;
}

}  // namespace

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
  int argc = 0;
  wchar_t **argv = CommandLineToArgvW(GetCommandLineW(), &argc);
  bool validate_only = argv && has_arg(argc, argv, L"--validate-only");
  try {
    int result = run(validate_only);
    if (argv) LocalFree(argv);
    return result;
  } catch (const std::exception &error) {
    if (argv) LocalFree(argv);
    std::wstring message;
    try {
      message = widen(error.what());
    } catch (...) {
      message = L"Erreur de lancement WebeeBlocks.";
    }
    if (!validate_only)
      MessageBoxW(nullptr, message.c_str(), L"WebeeBlocks", MB_OK | MB_ICONERROR);
    return 1;
  }
}
