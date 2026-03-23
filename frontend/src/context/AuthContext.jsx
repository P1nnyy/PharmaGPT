import React, { createContext, useContext, useState, useEffect } from 'react';
import { getUserProfile, setAuthToken as setAuthTokenAPI } from '../services/api';

const AuthContext = createContext();

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within AuthProvider');
    }
    return context;
};

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [isLoadingAuth, setIsLoadingAuth] = useState(true);

    useEffect(() => {
        const initAuth = async () => {
            try {
                const savedToken = localStorage.getItem('auth_token');
                if (savedToken) {
                    setAuthTokenAPI(savedToken);
                    const profile = await getUserProfile();
                    setUser(profile);
                }
            } catch (err) {
                console.error("Auth initialization failed:", err);
                setAuthTokenAPI(null);
                setUser(null);
            } finally {
                setIsLoadingAuth(false);
            }
        };
        initAuth();
    }, []);

    const value = {
        user,
        setUser,
        isLoadingAuth,
        setIsLoadingAuth,
        setAuthToken: setAuthTokenAPI
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};
