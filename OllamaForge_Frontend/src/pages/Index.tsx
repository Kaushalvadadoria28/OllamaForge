import { useAppContext } from "@/context/AppContext";
import Navbar from "@/components/Navbar/Navbar";
import Sidebar from "@/components/Sidebar/Sidebar";
import ChatArea from "@/components/Chat/ChatArea";
import LoadingOverlay from "@/components/UI/LoadingOverlay";

const Index = () => {
  const { isSessionReady, isConnected, sessionId } = useAppContext();

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-background">
      {!isConnected && sessionId && (
        <div className="bg-destructive/10 border-b border-destructive/30 px-4 py-2 text-center text-xs text-destructive font-medium">
          ⚠️ Cannot connect to OllamaForge backend at localhost:5000. Is it running?
        </div>
      )}
      <Navbar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <ChatArea />
      </div>
    </div>
  );
};

export default Index;
