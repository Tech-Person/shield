import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

// Use relative URL if REACT_APP_BACKEND_URL is not set (for self-hosted deployments)
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
const API = `${BACKEND_URL}/api`;

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);

  const getAuthHeaders = useCallback(() => {
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, [token]);

  const fetchUser = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }

    try {
      const response = await axios.get(`${API}/auth/me`, {
        headers: getAuthHeaders()
      });
      setUser(response.data);
    } catch (error) {
      console.error('Failed to fetch user:', error);
      localStorage.removeItem('token');
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, [token, getAuthHeaders]);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const login = async (username, password) => {
    const response = await axios.post(`${API}/auth/login`, {
      username,
      password
    });
    
    const { access_token, user: userData } = response.data;
    localStorage.setItem('token', access_token);
    setToken(access_token);
    setUser(userData);
    
    return userData;
  };

  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
  };

  const changePassword = async (currentPassword, newPassword) => {
    await axios.post(`${API}/auth/change-password`, {
      current_password: currentPassword,
      new_password: newPassword
    }, {
      headers: getAuthHeaders()
    });
    
    // Update user state to reflect password change
    setUser(prev => ({ ...prev, must_change_password: false }));
  };

  const refreshUser = async () => {
    await fetchUser();
  };

  const value = {
    user,
    token,
    loading,
    login,
    logout,
    changePassword,
    refreshUser,
    getAuthHeaders,
    isAdmin: user?.role === 'admin'
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
