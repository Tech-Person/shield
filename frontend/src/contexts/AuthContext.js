import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import api from '../lib/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const wsRef = useRef(null);
  const heartbeatRef = useRef(null);
  const afkTimeoutRef = useRef(null);

  const connectWebSocket = useCallback((token) => {
    if (wsRef.current) wsRef.current.close();
    const wsUrl = process.env.REACT_APP_BACKEND_URL.replace(/^http/, 'ws');
    const ws = new WebSocket(`${wsUrl}/ws/${token}`);
    ws.onopen = () => {
      heartbeatRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'heartbeat' }));
        }
      }, 30000);
    };
    ws.onclose = () => {
      clearInterval(heartbeatRef.current);
    };
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if ((data.type === 'new_message' || data.type === 'channel_message') && Notification?.permission === 'granted') {
          const msg = data.message;
          if (document.hidden && msg.sender_username) {
            new Notification(`${msg.sender_username}`, { body: msg.content?.substring(0, 100), icon: '/logo192.png', tag: msg.id });
          }
        }
      } catch {}
    };
    wsRef.current = ws;
    return ws;
  }, []);

  const checkAuth = useCallback(async () => {
    try {
      const { data } = await api.get('/auth/me');
      setUser(data.user);
      const tokenResp = await api.post('/auth/refresh');
      if (tokenResp.data.access_token) {
        connectWebSocket(tokenResp.data.access_token);
      }
    } catch {
      setUser(false);
    } finally {
      setLoading(false);
    }
  }, [connectWebSocket]);

  useEffect(() => {
    checkAuth();
    return () => {
      if (wsRef.current) wsRef.current.close();
      clearInterval(heartbeatRef.current);
      clearTimeout(afkTimeoutRef.current);
    };
  }, [checkAuth]);

  useEffect(() => {
    if (!user) return;
    const resetAfk = () => {
      clearTimeout(afkTimeoutRef.current);
      if (user.status === 'away') {
        api.put('/users/me/status', { status: 'online' }).catch(() => {});
      }
      afkTimeoutRef.current = setTimeout(() => {
        api.put('/users/me/status', { status: 'away' }).catch(() => {});
      }, 600000);
    };
    window.addEventListener('mousemove', resetAfk);
    window.addEventListener('keydown', resetAfk);
    resetAfk();
    return () => {
      window.removeEventListener('mousemove', resetAfk);
      window.removeEventListener('keydown', resetAfk);
      clearTimeout(afkTimeoutRef.current);
    };
  }, [user]);

  const login = async (email, password) => {
    const { data } = await api.post('/auth/login', { email, password });
    if (data.requires_2fa) return data;
    setUser(data.user);
    if (data.access_token) connectWebSocket(data.access_token);
    return data;
  };

  const verify2FA = async (code, tempToken) => {
    const { data } = await api.post(`/auth/verify-2fa?temp_token=${tempToken}`, { code });
    setUser(data.user);
    if (data.access_token) connectWebSocket(data.access_token);
    return data;
  };

  const register = async (username, email, password) => {
    const { data } = await api.post('/auth/register', { username, email, password });
    setUser(data.user);
    if (data.access_token) connectWebSocket(data.access_token);
    return data;
  };

  const logout = async () => {
    await api.post('/auth/logout');
    setUser(false);
    if (wsRef.current) wsRef.current.close();
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, verify2FA, register, logout, ws: wsRef, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be within AuthProvider');
  return context;
}
