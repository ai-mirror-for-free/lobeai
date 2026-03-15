// 简单的用户状态管理
import { reactive, readonly } from 'vue';

const state = reactive({
  userInfo: {
    id: null,
    name: '张三',
    email: 'zhangsan@example.com',
    role: '',
    profile_image_url: null,
    initials: 'ZS',
    registerDate: '2023年5月12日',
    avatar: null // 可选的头像URL
  },
  authInfo: {
    token: '',
    token_type: '',
    expires_at: null
  },
  permissions: {},
  subscriptionInfo: {
    planName: '专业版',
    planType: 'cyan', // 对应样式类
    expiryDate: '2024年12月31日',
    daysLeft: 245,
    isActive: true
  },
  isLoggedIn: false
});

export function useUserStore() {
  const login = (userData, authData = null, permissionsData = null) => {
    state.isLoggedIn = true;
    
    // 更新用户信息
    if (userData) {
      Object.assign(state.userInfo, {
        id: userData.id || state.userInfo.id,
        name: userData.name || state.userInfo.name,
        email: userData.email || state.userInfo.email,
        role: userData.role || state.userInfo.role,
        profile_image_url: userData.profile_image_url || state.userInfo.profile_image_url,
        initials: userData.initials || state.userInfo.initials,
        avatar: userData.avatar || userData.profile_image_url || state.userInfo.avatar
      });
    }
    
    // 更新认证信息
    if (authData) {
      Object.assign(state.authInfo, {
        token: authData.token || state.authInfo.token,
        token_type: authData.token_type || state.authInfo.token_type,
        expires_at: authData.expires_at || state.authInfo.expires_at
      });
    }
    
    // 更新权限信息
    if (permissionsData) {
      state.permissions = permissionsData;
    }
  };

  const logout = () => {
    state.isLoggedIn = false;
    // 重置为默认用户数据
    state.userInfo = {
      id: null,
      name: '张三',
      email: 'zhangsan@example.com',
      role: '',
      profile_image_url: null,
      initials: 'ZS',
      registerDate: '2023年5月12日',
      avatar: null
    };
    state.authInfo = {
      token: '',
      token_type: '',
      expires_at: null
    };
    state.permissions = {};
  };

  const updateSubscription = (subscriptionData) => {
    Object.assign(state.subscriptionInfo, subscriptionData);
  };

  // 添加一个方法用于获取token
  const getToken = () => {
    return state.authInfo.token;
  };

  // 添加方法用于获取用户邮箱
  const getUserEmail = () => {
    return state.userInfo.email;
  };

  // 添加方法用于获取用户名
  const getUserName = () => {
    return state.userInfo.name;
  };

  return {
    state: readonly(state),
    login,
    logout,
    updateSubscription,
    getToken,
    getUserEmail,
    getUserName
  };
}