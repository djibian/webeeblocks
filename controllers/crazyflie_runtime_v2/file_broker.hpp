#ifndef WEBEEBLOCKS_FILE_BROKER_HPP
#define WEBEEBLOCKS_FILE_BROKER_HPP

#include <cstddef>
#include <memory>
#include <string>

namespace webeeblocks {

class FileDialogProvider {
public:
  virtual ~FileDialogProvider() = default;
  virtual std::string name() const = 0;
};

std::unique_ptr<FileDialogProvider> createQtFileDialogProvider();

class FileBroker {
public:
  explicit FileBroker(std::unique_ptr<FileDialogProvider> provider);
  ~FileBroker();

  FileBroker(const FileBroker &) = delete;
  FileBroker &operator=(const FileBroker &) = delete;

  // Returns true only for a syntactically valid broker request. The response
  // is left empty for messages owned by another WWI protocol.
  bool handleMessage(const char *message, char *response, std::size_t responseSize) const;

private:
  std::unique_ptr<FileDialogProvider> mProvider;
};

}  // namespace webeeblocks

#endif
