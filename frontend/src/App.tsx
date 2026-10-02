import { Routes, Route } from "react-router-dom";
import { ProfileProvider } from "./context/ProfileContext";
import { ToastProvider } from "./context/ToastContext";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import BrowsePage from "./pages/BrowsePage";
import ChatPage from "./pages/ChatPage";
import ProfilePage from "./pages/ProfilePage";
import RegisterPage from "./pages/RegisterPage";
import CompleteProfilePage from "./pages/CompleteProfilePage";
import UserPage from "./pages/UserPage";
import VerifyPage from "./pages/VerifyPage"
import ProtectedRoute from "./components/ProtectedRoute";
import GuestRoute from "./components/GuestRoute";
import OnboardingRoute from "./components/OnboardingRoute";

function App() {
    return (
            <ProfileProvider>
                <ToastProvider>
                    <Routes>
                        <Route path="/" element={<GuestRoute><LandingPage /></GuestRoute>} />
                        <Route path="/browse" element={<ProtectedRoute><BrowsePage /></ProtectedRoute>} />
                        <Route path="/chat" element={<ProtectedRoute><ChatPage /></ProtectedRoute>} />
                        <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
                        <Route path="/complete-profile" element={<OnboardingRoute><CompleteProfilePage /></OnboardingRoute>} />
                        <Route path="/users/:id" element={<ProtectedRoute><UserPage /></ProtectedRoute>} />
                        <Route path="/login" element={<GuestRoute><LoginPage /></GuestRoute>} />
                        <Route path="/verify" element={<VerifyPage />} />
                        <Route path="/register" element={<GuestRoute><RegisterPage /></GuestRoute>} />
                    </Routes>
                </ToastProvider>
            </ProfileProvider>
    );
}

export default App;
