import { Routes, Route } from "react-router-dom";
import { ProfileProvider } from "./context/ProfileContext";
import { ToastProvider } from "./context/ToastContext";
import { ChatProvider } from "./context/ChatContext";
import { BrowseProvider } from "./context/BrowseContext";
import AnimatedOutlet from "./components/AnimatedOutlet";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import BrowsePage from "./pages/BrowsePage";
import ChatPage from "./pages/ChatPage";
import ProfilePage from "./pages/ProfilePage";
import ProfilePreviewPage from "./pages/ProfilePreviewPage";
import RegisterPage from "./pages/RegisterPage";
import CompleteProfilePage from "./pages/CompleteProfilePage";
import UserPage from "./pages/UserPage";
import VerifyPage from "./pages/VerifyPage"
import ProtectedRoute from "./components/ProtectedRoute";
import GuestRoute from "./components/GuestRoute";
import OnboardingRoute from "./components/OnboardingRoute";
import { NotificationProvider } from "./context/NotificationContext";
import NotificationPage from "./pages/NotificationPage";

function App() {
    return (
            <ProfileProvider>
                <ToastProvider>
                    <ChatProvider>
                        <NotificationProvider>
                            <Routes>
                                <Route path="/" element={<GuestRoute><LandingPage /></GuestRoute>} />
                                <Route element={<ProtectedRoute><BrowseProvider><AnimatedOutlet /></BrowseProvider></ProtectedRoute>}>
                                    <Route path="/browse" element={<BrowsePage />} />
                                    <Route path="/users/:id" element={<UserPage />} />
                                </Route>
                                <Route path="/chat/:id?" element={<ProtectedRoute><ChatPage /></ProtectedRoute>} />
                                <Route path="/notification" element={<ProtectedRoute><NotificationPage /></ProtectedRoute>} />
                                <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
                                <Route path="/profile/preview" element={<ProtectedRoute><ProfilePreviewPage /></ProtectedRoute>} />
                                <Route path="/complete-profile" element={<OnboardingRoute><CompleteProfilePage /></OnboardingRoute>} />
                                <Route path="/login" element={<GuestRoute><LoginPage /></GuestRoute>} />
                                <Route path="/verify" element={<VerifyPage />} />
                                <Route path="/register" element={<GuestRoute><RegisterPage /></GuestRoute>} />
                            </Routes>
                        </NotificationProvider>
                    </ChatProvider>
                </ToastProvider>
            </ProfileProvider>
    );
}

export default App;
