import { Routes, Route } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import BrowsePage from "./pages/BrowsePage";
import ChatPage from "./pages/ChatPage";
import ProfilePage from "./pages/ProfilePage";
import RegisterPage from "./pages/RegisterPage";
import UserPage from "./pages/UserPage";
import VerifyPage from "./pages/VerifyPage"
import ProtectedRoute from "./components/ProtectedRoute";

function App() {
    return (
            <Routes>
                <Route path="/" element={<LandingPage />} />
                <Route path="/browse" element={<ProtectedRoute><BrowsePage /></ProtectedRoute>} />
                <Route path="/chat" element={<ProtectedRoute><ChatPage /></ProtectedRoute>} />
                <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
                <Route path="/users/:id" element={<ProtectedRoute><UserPage /></ProtectedRoute>} />
                <Route path="/login" element={<LoginPage />} />
                <Route path="/verify" element={<VerifyPage />} />
                <Route path="/register" element={<RegisterPage />} />
            </Routes>
    );
}

export default App;
