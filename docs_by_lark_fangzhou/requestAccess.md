requestAuthCode
最后更新于 2025-04-09
requestAuthCode(Object object) 用于获取网页应用免登授权码，从而实现网页应用的用户免登流程。

该接口为历史版本，已停止维护，推荐你使用requestAccess。关于网页应用免登流程的操作方法，可参见步骤三：免登流程（可选）。
你无需进行网页应用鉴权即可调用该接口，但需要保证在 window.h5sdk.ready 的回调函数触发后调用该接口。
window.h5sdk.ready 由 H5 JSSDK 提供，用于 JSSDK 初始化完成后的回调。关于 JSSDK 的相关说明，可参见开放接口。

# requestAccess(Object object)

增量授予应用访问权限

## 支持说明

应用能力 | Android | iOS | PC | Harmony | 预览效果
---|---|---|---|---|---
小程序 | V6.9.0+ | V6.9.0+ | V6.9.0+ | V7.35.0+ | 预览
网页应用 | V6.9.0+ | V6.9.0+ | V6.9.0+ | V7.35.0+ | 预览

## 输入
继承[标准对象输入](https://open.feishu.cn/document/uYjL24iN/ukzNy4SO3IjL5cjM)，扩展属性描述：

名称 | 数据类型 | 必填 | 默认值 | 描述
---|---|---|---|---
scopeList | Array<string\> | 是 | \- | 授予应用[权限列表](https://open.feishu.cn/document/ukTMukTMukTM/uYTM5UjL2ETO14iNxkTN/scope-list)<br><md-alert><br>- 空数组表示：仅授予应用获取用户凭证信息权限 [获取登录用户信息](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/authen-v1/user_info/get)<br>- 当传入增量权限后，用户在飞书客户端内使用应用时需要先完成授权。
state | string | 否 | \- | 用来维护请求和回调状态的附加字符串， 在授权完成回调时会附加此参数，应用可以根据此字符串来判断上下文关系。详见[获取授权登录授权码](https://open.feishu.cn/document/common-capabilities/sso/api/obtain-oauth-code)
appID | string | 否 | \- | 应用ID ( 网页应用必须传 )

## 输出
继承[标准对象输出](https://open.feishu.cn/document/uYjL24iN/ukzNy4SO3IjL5cjM#8c92acb8)，`success`返回对象的扩展属性：

名称 | 数据类型 | 描述
---|---|---
code | string | 临时登录凭证，有效期 3 分钟，只能使用一次
state | string | 用来维护请求和回调状态的附加字符串， 在授权完成回调时会附加此参数，应用可以根据此字符串来判断上下文关系。详见[获取授权登录授权码](https://open.feishu.cn/document/common-capabilities/sso/api/obtain-oauth-code)

## 示例代码
```js
tt.requestAccess({
  scopeList: ["contact:contact.base:readonly", "docs_tool:docs_tool"],
  appID: "cli_xxx", // 网页应用必传
  success(res) {
    console.log(JSON.stringify(res));
  },
  fail(res) {
    console.log(`requestAccess fail: ${JSON.stringify(res)}`);
  },
});
```

`success`返回对象示例：

```json
{
  "errMsg": "requestAccess:ok",
  "code": "1d34ef4fdfdf12332fffd"
}
```

**errno 错误码**

关于 Errno 错误码的详细说明以及通用错误码列表，可参见[Errno 错误码](https://open.feishu.cn/document/uYjL24iN/uAjMuAjMuAjM/errno)。