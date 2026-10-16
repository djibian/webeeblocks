// Test-only provider: real OS pipe wait released by an independent thread.
// All provider entry points, including construction/metadata/release, block.
#include "file_broker.hpp"
#include <chrono>
#include <thread>
#include <unistd.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif
#include <map>
static std::string file_probe;
static int file_creations=0,file_calls=0,file_denied=0;
static std::map<int,bool> file_expected;
static bool file_startup(){return file_probe=="startup-reset";}
static bool file_safe(){return (!takeoff && !teleports) || reset_ok;}
static void file_wait(const char* operation){
 assert(file_safe());
 const long long before=tick;
 int fds[2];
#ifdef _WIN32
 assert(_pipe(fds,4096,_O_BINARY)==0);
#else
 assert(pipe(fds)==0);
#endif
 const auto start=std::chrono::steady_clock::now();
 std::thread release([&]{
  // This wait establishes the blocking-provider test precondition. Release
  // only after the observed monotonic deadline, including on Windows timers;
  // a single relative sleep is not itself evidence that 100 ms have elapsed.
  const auto release_at=start+std::chrono::milliseconds(100);
  while(std::chrono::steady_clock::now()<release_at)
   std::this_thread::sleep_for(std::chrono::milliseconds(1));
  assert(write(fds[1],"R",1)==1);
 });
 std::printf("GP_U_FILE_ENTER t=%lld op=%s\n",tick,operation);
 char value=0;assert(read(fds[0],&value,1)==1 && value=='R');
 release.join();assert(close(fds[0])==0 && close(fds[1])==0);
 const auto elapsed=std::chrono::steady_clock::now()-start;
 std::printf("GP_U_FILE_WAIT before=%lld after=%lld elapsed_us=%lld\n",before,tick,
  static_cast<long long>(std::chrono::duration_cast<std::chrono::microseconds>(elapsed).count()));
 assert(tick==before && elapsed>=std::chrono::milliseconds(90));
 std::printf("GP_U_FILE_RELEASE t=%lld op=%s\n",tick,operation);
 ++file_calls;
}
class BlockingFileProvider : public webeeblocks::FileDialogProvider {
public:
 std::string name() const override {file_wait("CAPABILITIES");return "blocking-pipe";}
 webeeblocks::OpenFileResult open() override {
  file_wait("OPEN");return {webeeblocks::FileOperationStatus::Ok,"ref","probe.wbb","{}",""};
 }
 webeeblocks::SaveFileResult saveAs(const std::string& name,const std::string& bytes) override {
  assert(name=="probe.wbb" && bytes=="{}");file_wait("SAVE_AS");
  return {webeeblocks::FileOperationStatus::Ok,"ref",name,""};
 }
 webeeblocks::SaveFileResult save(const std::string& ref,const std::string& bytes) override {
  assert(ref=="ref" && bytes=="{}");file_wait("SAVE");
  return {webeeblocks::FileOperationStatus::Ok,"ref","probe.wbb",""};
 }
 void release(const std::string& ref) override {assert(ref=="ref");file_wait("RELEASE");}
};
struct WbFileBroker {
 webeeblocks::FileBroker broker{std::make_unique<BlockingFileProvider>()};
 std::string response;
};
extern "C" WbFileBroker* wb_file_broker_create_qt(){
 if(file_probe.empty())return nullptr;
 file_wait("CREATE");++file_creations;return new WbFileBroker;
}
extern "C" void wb_file_broker_destroy(WbFileBroker* broker){delete broker;}
extern "C" const char* wb_file_broker_handle_message(WbFileBroker* broker,const char* message){
 assert(broker);broker->response.clear();
 assert(broker->broker.handleMessage(message,&broker->response));
 return broker->response.empty()?nullptr:broker->response.c_str();
}
static const char* file_requests(int& index){
 if(file_probe.empty())return nullptr;
 const bool transition=tick==2048 || (!file_startup() && tick==reset_tick());
 const bool selected=transition || (file_startup()?
  (tick==2080 || tick==2528 || tick==2560 || tick==2592 || tick==2624):
  (tick==2656 || tick==212016 || tick==212048 || tick==212080 ||
   tick==212688 || tick==212752 || tick==213008 || tick==213232 ||
   tick==213264 || tick==213296 || tick==213520));
 if(!selected)return nullptr;
 const bool before=!(tick==2048 && file_probe=="cold");
 const int pre=before?5:0;
 // Runtime request 0 between the two batches exercises same-tick transitions.
 int operation=-1;
 if(index<pre)operation=index;
 else if(transition && index>pre && index<=pre+5)operation=index-pre-1;
 if(operation>=0){
  static const char* commands[]={"CAPABILITIES","OPEN","SAVE_AS cHJvYmUud2Ji e30=","SAVE ref e30=","RELEASE ref"};
  static std::string request;
  const int id=1000+static_cast<int>(file_expected.size());
  file_expected[id]=file_safe();
  request="WEBEEBLOCKS_FILE_BROKER_V1 REQUEST "+std::to_string(id)+" "+commands[operation];
  return request.c_str();
 }
 index-=pre+(transition && index>pre+5?5:0);
 return nullptr;
}
static void file_verify(){
 if(file_probe.empty())return;
 int allowed=0;
 for(const auto& item:file_expected){
  const std::string prefix="WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE "+std::to_string(item.first)+" ";
  int count=0;
  for(const auto& response:replies)if(response.find(prefix)==0){
   ++count;
   if(!item.second)assert(response==prefix+"ERR BUSY");
   else assert(response.find("ERR ")==std::string::npos);
  }
  assert(count==1);
  if(item.second)++allowed;else ++file_denied;
 }
 assert(file_denied>=15);
 assert(file_creations==(allowed?1:0));
 assert(file_calls==allowed+file_creations);
 if(file_probe=="warm" || file_startup())assert(allowed>=10);
 char evidence[256];
 std::snprintf(evidence,sizeof(evidence),"GP_U_FILE_PASS probe=%s requests=%zu denied=%d calls=%d creations=%d claim=blocking-provider-composition",
  file_probe.c_str(),file_expected.size(),file_denied,file_calls,file_creations);
 const char* path=std::getenv("GP_U_FILE_OUT");
 if(path){FILE* f=std::fopen(path,"w");assert(f);assert(std::fprintf(f,"%s\n",evidence)>0);assert(std::fclose(f)==0);}
 std::puts(evidence);
}
