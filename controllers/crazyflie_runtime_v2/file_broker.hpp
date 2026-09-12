#ifndef WEBEEBLOCKS_FILE_BROKER_HPP
#define WEBEEBLOCKS_FILE_BROKER_HPP

#include <cstddef>
#include <memory>
#include <string>

namespace webeeblocks {

enum class FileOperationStatus { Ok, Cancelled, Error };

struct OpenFileResult {
  FileOperationStatus status = FileOperationStatus::Error;
  std::string reference;
  std::string name;
  std::string bytes;
  std::string errorCode = "IO_ERROR";
};

struct SaveFileResult {
  FileOperationStatus status = FileOperationStatus::Error;
  std::string reference;
  std::string name;
  std::string errorCode = "IO_ERROR";
};

class FileDialogProvider {
public:
  virtual ~FileDialogProvider() = default;
  virtual std::string name() const = 0;
  virtual OpenFileResult open() = 0;
  virtual SaveFileResult saveAs(const std::string &suggestedName, const std::string &bytes) = 0;
  virtual SaveFileResult save(const std::string &reference, const std::string &bytes) = 0;
};

std::unique_ptr<FileDialogProvider> createQtFileDialogProvider();

class FileBroker {
public:
  static constexpr std::size_t kMaxProjectBytes = 4u * 1024u * 1024u;

  explicit FileBroker(std::unique_ptr<FileDialogProvider> provider);
  ~FileBroker();

  FileBroker(const FileBroker &) = delete;
  FileBroker &operator=(const FileBroker &) = delete;

  // Returns false only when message is not a file-broker message. A broker
  // message is always consumed; malformed requests receive a fail-closed error
  // whenever a valid request id can be recovered.
  bool handleMessage(const char *message, std::string *response);

private:
  std::unique_ptr<FileDialogProvider> mProvider;
};

}  // namespace webeeblocks
#endif
