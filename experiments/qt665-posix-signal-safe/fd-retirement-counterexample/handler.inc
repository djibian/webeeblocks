static volatile sig_atomic_t gQuitNotificationFd = -1;
static void quitApplication(int sig) {
  const int savedErrno = errno;
  const sig_atomic_t fd = gQuitNotificationFd;
  if (fd >= 0) {
    const unsigned char notification = static_cast<unsigned char>(sig);
    (void)write(static_cast<int>(fd), &notification, sizeof(notification));
  }
  errno = savedErrno;
}

static bool configureQuitPipeFd(int fd) {
  const int flags = fcntl(fd, F_GETFL);
  const int descriptorFlags = fcntl(fd, F_GETFD);
  return flags != -1 && descriptorFlags != -1 &&
         fcntl(fd, F_SETFL, flags | O_NONBLOCK) != -1 &&
         fcntl(fd, F_SETFD, descriptorFlags | FD_CLOEXEC) != -1;
}
