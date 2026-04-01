# 概览

本文介绍如何快速开发一个飞书客户端内的企业自建网页应用，本示例使用飞书客户端 JSSDK，在鉴权完成后，调用了 [获取已登录用户的基本信息](https://open.feishu.cn/document/uYjL24iN/ucjMx4yNyEjL3ITM)、[弹出消息提示框](https://open.feishu.cn/document/uYjL24iN/ugzMy4COzIjL4MjM) JSAPI。通过该教程，您可以了解开发及上线网页应用的完整流程，并理解鉴权的基本原理。

## 什么是网页应用？

网页（Web）应用指的是用 H5 方式开发，可以运行在飞书客户端内的应用。网页应用可以调用丰富的飞书客户端开放接口（客户端 API，也称为 JSAPI），这些接口包含手机系统功能以及通讯录、云文档等飞书客户端功能。同时，网页应用也可以享受到客户端侧的性能优化，使你的网页应用能够接近原生体验。
JSAPI 调用依赖官方提供的工具包 JSSDK，使用时需在调用 JSAPI 的页面引入。
更多介绍信息，参考[网页应用简介](https://open.feishu.cn/document/uYjL24iN/uMTMuMTMuMTM/introduction)。

## 操作流程

本文涉及的操作流程如下图：

![image.png](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/1d1dd7102ec4fd7dd259a2872f824255_I212j0oZGb.png?height=208&lazyload=true&width=652)

## 实现效果

按照本教程操作最终可以实现如下图的示意效果。

![](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/575e1c93a4d19592fa6fdd4fca17b526_wAkAmcdAIC.png?height=1532&lazyload=true&maxWidth=750&width=2352)

# 准备工作

在正式开发之前，你需要完成以下准备工作：

- [创建](https://www.feishu.cn/hc/zh-CN/articles/360043741453)或[加入](https://www.feishu.cn/hc/zh-CN/articles/360043496893)飞书企业。

- 本文提供 Python 语言的[示例代码](https://sf3-cn.feishucdn.com/obj/open-platform-opendoc/8651c8d456469c0881343f9b7d006833.zip)，需在本地安装 [Python3](https://www.python.org/) 运行环境。

# 步骤一：创建测试应用

通过本步骤您将创建一个测试应用，用于构建网页应用。

## 操作步骤

1. 登录[飞书开发者后台](https://open.feishu.cn/app)。

2. 在开发者后台首页，单击 **创建企业自建应用**，填写应用名称、描述以及图标信息，然后单击 **创建**。

![](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/8024a7e2fd42054b4653d54fc884ae54_qrxx8WHPHk.png?height=1526&lazyload=true&maxWidth=600&width=2512)

3. 在应用详情页左侧导航栏，进入 **测试企业和人员** 页面，并在页面右上角单击 **创建测试企业**。
为了满足开发测试阶段频繁变更配置的需求，飞书开放平台提供了[测试企业与人员功能](https://open.feishu.cn/document/home/introduction-to-custom-app-development/testing-enterprise-and-personnel-functions)。在开发阶段，推荐开发者使用测试版应用，此**版本中涉及的权限和配置变更都会直接生效，无需管理员审核**，客户端的测试也将在测试租户进行。在所有的开发测试完成之后，切换、手动同步到正式版应用，仅提交一次审核即可，大大加速了开发效率，也降低了对管理员的打扰。

4. 在 **创建测试企业** 对话框，填写 **测试企业名称**、**手机号**、**验证码**，并单击 **确认创建**。

![](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/85af43ae4f1337a78e80d3608c590449_kMNHgsBwEY.png?height=1378&lazyload=true&maxWidth=600&width=3572)

5. 创建测试企业后，在 **操作** 列，单击 **关联应用**。

![](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/341586fdf85d2297f0eb9ef2e85a1b09_QPkEpMjPuA.png?height=552&lazyload=true&maxWidth=600&width=2950)

6. 测试企业关联应用后，在页面顶部切换企业应用为测试版应用。

![](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/5d934d17429ce3722de3fafa4ae4356e_zpaH0l0A1Y.png?height=804&lazyload=true&maxWidth=600&width=3576)

# 步骤二：下载并配置示例代码

你需要先获取应用凭证，然后下载示例代码，并将应用凭证配置在代码的相应位置，最后为示例代码配置运行环境。

## 获取应用凭证

1. 在[开发者后台](https://open.feishu.cn/app/)，点击应用名称或应用图标进入应用详情页。

![image.png](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/1dd0ed243f124d8001901522bd196626_6KICVofqyj.png?height=1460&lazyload=true&maxWidth=600&width=2462)

2. 在左侧导航栏点击进入 **凭证与基础信息** 页面，在 **应用凭证** 中获取 `App ID` 和 `App Secret` 值。

![image.png](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/1324a903a8c08a27836316a6bc2011f7_hHBttFt5ic.png?height=1200&lazyload=true&maxWidth=600&width=2670)

## 下载代码示例并配置应用凭证

1. 使用本地的命令行工具，下载并解压 [示例代码](https://sf3-cn.feishucdn.com/obj/open-platform-opendoc/8651c8d456469c0881343f9b7d006833.zip)，并进入 `python` 目录。

各模块代码逻辑的介绍，参考[示例代码介绍](https://open.feishu.cn/document/home/integrating-web-apps-in-5-minutes/debug-and-release)。

- **Mac/Linux**
      ```
      curl  https://sf3-cn.feishucdn.com/obj/open-platform-opendoc/8651c8d456469c0881343f9b7d006833.zip -o web_app_with_jssdk.zip
      unzip web_app_with_jssdk.zip
      cd web_app_with_jssdk/python
      ```
    - **Windows**：依次运行以下命令

1. `curl  https://sf3-cn.feishucdn.com/obj/open-platform-opendoc/8651c8d456469c0881343f9b7d006833.zip -o web_app_with_jssdk.zip`
    	2. `tar -xzvf web_app_with_jssdk.zip`

如果本地未安装 `tar`，可直接找到压缩包点击解压，或使用已安装的解压工具自行解压。	

3. `cd web_app_with_jssdk/python`

2. 修改 `.env` 文件中应用凭证数据为实际应用凭证信息。

```
    APP_ID=cli_9fxxxx00b
    APP_SECRET=EX6xxxxOF
    ```

## 启动本地服务

1. 创建并激活一个新的虚拟环境。

- **Mac/** **Linux**
      ```
      python3 -m venv venv
      . venv/bin/activate
      ```
    - **Windows**：依次运行以下命令

1. `python3 -m venv venv`
		2. `venv\Scripts\activate`

激活后，终端会显示虚拟环境的名称。

![](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/9a40883c5c6ada83f03f534456e21a19_X4kHriZmBl.png?height=178&lazyload=true&maxWidth=600&width=820)

2. 安装依赖。
    ```
    pip install -r requirements.txt
    ```
3. 启动项目并获取内网访问地址。

```
    python3 server.py
    ```

启动后会生成临时域名，如下图所示，仅在同一局域网内有效。

![](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/de113c3631feeea9e6a62277138c2196_RiszAgYTKZ.png?height=590&lazyload=true&maxWidth=600&width=1442)

# 步骤三：配置网页应用

运行示例代码获取应用域名信息后，返回飞书开发者后台配置网页应用。

## 操作步骤

1. 在 [开发者后台](https://open.feishu.cn/app/)，从左侧导航栏点击**添加应用能力**，然后选择 **网页应用** 点击**添加能力**。

2. 在 **网页配置** 中填写 **桌面端主页** 和 **移动端主页**， 填写在步骤二中获取的临时内网访问地址，例如 `http://10.86.120.185:3000` 。 warning
正式上线应用时，此处配置主页地址需为**公网地址**。为了快速体验接入流程，本示例中暂时先使用本地环境。 

![image.png](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/d397f521373055e77d57b508d1e5b879_Gi06Dj0Gzq.png?height=1560&lazyload=true&maxWidth=600&width=2972)

3. 从左侧导航栏点击 **安全设置**，在 **H5可信域名** 中添加需要调用 JSAPI 接口的页面所在的 `域名:端口号`。

本示例中配置 H5 可信域名为上述获取的临时内网访问地址，即 `http://10.86.120.185:3000`。

![image.png](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/19f53983ef21c029edb115523b44f9d1_nFzacC8SS5.png?height=1696&lazyload=true&maxWidth=600&width=2964)

# 步骤四：体验网页应用
对于测试版应用来说，仅测试企业的 **创建者** 及 **测试人员** 可以访问该应用。用户可以通过飞书客户端（移动或 PC 端）内体验和调试网页应用。

## 操作步骤

1. 打开飞书客户端（移动或 PC 端），在顶部搜索框中搜索应用名称 ，点开网页应用。

![](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/25afbd50baaa4b8ec33a20a4b8e09ea6_WqozEdnEbc.png?height=718&lazyload=true&maxWidth=600&width=1952)

2. 在弹出的授权窗口中，点击**允许**。

![](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/0ddca7e05ec2ec91f5e3e5d5cc5658fe_5r66c92zX1.png?height=1512&lazyload=true&maxWidth=600&width=2734)

若正常运行，会显示当前客户端内登录用户的姓名与头像。

![](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/df12320515d1edae1d37a6346b169162_R1s0qcOZeP.png?height=1530&lazyload=true&maxWidth=600&width=2730)

3. 点击页面上的 `vConsole` 进行简单的本地调试。
用移动端调试时，手机和服务所运行的 PC 端需要在**同一个局域网内**。

![](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/e093862b0219b7007f144fcbe2ba62d8_gwW7BeILWb.png?height=1534&lazyload=true&maxWidth=600&width=2742)

# 示例代码介绍

本教程提供的示例代码基于 [Python 3](https://www.python.org/) 环境和 [Flask](https://dormousehole.readthedocs.io/en/latest/) 框架编写。

## 项目结构

```
.
├── README.zh.md     ----- 说明文档
├── public
│   ├── svg     ----- 前端图形文件
│   ├── index.css     ----- 前端展示样式
│   ├── index.js     ----- 前端交互代码
├── templates
│   ├── index.html     ----- 前端用户信息展示页面
├── auth.py     ----- 服务端获取jsapi_ticket等
├── server.py     ----- 服务端核心业务代码
├── requirements.txt     ----- 环境配置文件
└── .env     ----- 全局默认配置文件，主要存储App ID和App Secret等
```

项目结构说明：

- public 和 templates 节点：前端模块，主要功能是调取客户端 API（JSAPI）获取用户信息、展示用户信息。
- 其他节点：服务端模块，使用 Flask 构建，主要功能如下。

- 使用 App ID 和 App Secret 获取 tenant_access_token；
    - 使用 tenant_access_token 获取 jsapi_ticket；
    - 使用 jsapi_ticket、随机字符串、当前时间戳、当前鉴权的网页 URL 生成签名 signature。更多鉴权信息，可参见[组件 SDK 鉴权流程](https://open.feishu.cn/document/uYjL24iN/uUDO3YjL1gzN24SN4cjN)。

## 代码解析

业务处理的逻辑图如下所示。

![](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/a7a45ab6607d0392767198dd563fb21f_wEg4mBAdVI.png?height=434&lazyload=true&width=1351)

### 服务端代码

1. 获取 access_token。

调用服务端 API 获取应用资源时，需要通过 access_token 来判断调用者身份。企业自建应用可通过[自建应用获取 tenant_access_token](https://open.feishu.cn/document/ukTMukTMukTM/ukDNz4SO0MjL5QzM/auth-v3/auth/tenant_access_token_internal) 接口获取。
access_token 存在有效期，因此开发者需要在自己的服务端及时刷新凭证，以防止过期。access_token 有效期为 2 小时。再次调用`自建应用获取 tenant_access_token`接口时：

- 如果 access_token 剩余有效时间大于半小时，接口返回的 access_token 和旧的 access_token 值相同，且不续期。
- 如果 access_token 剩余有效时间小于半小时，接口会返回一个新的 access_token，与此同时旧的 access_token 依然有效，直到其原定期限过期。

示例代码路径：web_app_with_jssdk/python/auth.py。在 auth.py 文件中，Auth 类的`authorize_tenant_access_token`方法实现了 access_token 的获取。

```Python
def authorize_tenant_access_token(self):
    # 获取tenant_access_token，基于开放平台能力实现，具体参考文档：https://open.feishu.cn/document/ukTMukTMukTM/ukDNz4SO0MjL5QzM/auth-v3/auth/tenant_access_token_internal
    url = "{}{}".format(self.feishu_host, TENANT_ACCESS_TOKEN_URI)
    req_body = {"app_id": self.app_id, "app_secret": self.app_secret}
    response = requests.post(url, req_body)
    Auth._check_error_response(response)
    self.tenant_access_token = response.json().get("tenant_access_token")
```

2. 获取 jsapi_ticket。

jsapi_ticket 代表网页应用调用飞书 JSAPI 的临时凭证。你可利用上述获取的 access_token，调用[获取 jsapi_ticket](https://open.feishu.cn/document/ukTMukTMukTM/uYTM5UjL2ETO14iNxkTN/h5_js_sdk/authorization) 接口获得 jsapi_ticket。
- 应用获取的 jsapi_ticket 存在有效期，过期时间为接口返回数据中的 `expire_in` 字段对应的秒数。当你再次调用`获取 jsapi_ticket`接口时：

- 如果 jsapi_ticket 剩余有效时间大于半小时，接口返回的 jsapi_ticket 和旧的 jsapi_ticket 值相同，但旧的 jsapi_ticket 不会续期。
	- 如果 jsapi_ticket 剩余有效时间小于半小时，接口返回一个新的 jsapi_ticket，与此同时旧的 jsapi_ticket 依然有效，到其原定期限过期。

- 由于获取 jsapi_ticket 的 API 调用次数有限，频繁刷新 jsapi_ticket 会导致 API 调用受限，影响自身业务，所以开发者在使用时需要缓存 jsapi_ticket，缓存有效期可根据接口返回的 `expire_in` 字段对应的秒数来设置，并不需要每次都从接口拉取。

- 如果获取 jsapi_ticket 失败时，服务端返回的错误码为 99991401（errorMsg: ip %s is denied by app setting），说明当前 IP 被白名单限制。开启 IP 白名单后，所有接口请求都会检查来源 IP，仅白名单中的来源请求可以正常调用开放平台 API，非白名单中的请求则会被拒绝。
<br>
前往 [开发者后台](https://open.feishu.cn/app) > 应用详情页 > **安全设置** > **IP 白名单** 中可查看是否配置了 IP 白名单，或者自行配置业务所需的 IP 白名单范围。

示例代码路径：web_app_with_jssdk/python/auth.py。在 auth.py 文件中，Auth 类的`get_ticket`方法实现了 jsapi_ticket 的获取。

```Python
def get_ticket(self):
    # 获取jsapi_ticket，具体参考文档：https://open.feishu.cn/document/ukTMukTMukTM/uYTM5UjL2ETO14iNxkTN/h5_js_sdk/authorization
    self.authorize_tenant_access_token()
    url = "{}{}".format(self.feishu_host, JSAPI_TICKET_URI)
    headers = {
        "Authorization": "Bearer " + self.tenant_access_token,
        "Content-Type": "application/json",
    }
    resp = requests.post(url=url, headers=headers)
    Auth._check_error_response(resp)
    return resp.json().get("data").get("ticket", "")
```

3. 生成签名并返回鉴权参数。

获取 jsapi_ticket 后，生成 JSSDK 权限验证的签名。

**获取签名所需的参数说明**

参数 | 数据类型 | 示例值 | 描述
---|---|---|---
noncestr | string | Y7a8KkqX041bsSwT | 随机字符串。
jsapi_ticket | string | 617bf955832a4d4d80d9d8d85917a427 | 上一步骤获得的 ticket。
timestamp | number | 1510045655000 | 当前时间戳，毫秒级。<br>数据类型不能使用 string 类型。
url | string | https://example.cn/test/1234/content.html | 当前网页的 URL（可以是本地局域网网址），不包含#及其后面部分。这里url建议由前端通过接口传给后端，前端应当使用`encodeURIComponent(location.href.split("#")[0]`获取当前页面url是最准确的，不要手写或者在此基础上拼接参数，以免验签时候url不匹配导致验签失败。

**签名生成规则**

将所有待签名参数按照字段名的 ASCII 码从小到大排序（字典序）后，使用 URL 键值对的格式，即`key1=value1&key2=value2…`拼接成字符串 verifyStr，对拼成的字符串 verifyStr 做 sha1 加密，得到签名 signature。
- 出于安全考虑，开发者必须在服务器端实现签名的逻辑。
- 拼接字符串 verifyStr 的所有参数名均为小写字符。
- 字段名和字段值都采用原始值，不进行 URL 转义。

示例：

- 根据 jsapi_ticket、noncestr、timestamp、url 的顺序拼接成字符串 verifyStr。

```
  jsapi_ticket=617bf955832a4d4d80d9d8d85917a427&noncestr=Y7a8KkqX041bsSwT&timestamp=1510045655000&url=https://example.cn/test/1234/content.html
  ```

- 对 verifyStr 进行 sha1 签名，得到 signature。

```
  40a68999ecf7e05907edba43b31a50fd1830c777
  ```

示例代码路径：web_app_with_jssdk/python/server.py。在 server.py 文件中，`get_config_parameters`方法利用前端传来的、需要进行鉴权的网页 URL，生成签名 signature，并将鉴权所需参数返回给前端。

```Python
# 获取并返回接入方前端将要调用的config接口所需的参数
@app.route("/get_config_parameters", methods=["GET"])
def get_config_parameters():    
    # 接入方前端传来的需要鉴权的网页url
    url = request.args.get("url")
    # 初始化Auth类时获取的jsapi_ticket
    ticket = auth.get_ticket()
    # 当前时间戳，毫秒级
    timestamp = int(time.time()) * 1000
    # 拼接成字符串 
    verify_str = "jsapi_ticket={}&noncestr={}&timestamp={}&url={}".format(
        ticket, NONCE_STR, timestamp, url
    )
    # 对字符串做sha1加密，得到签名signature
    signature = hashlib.sha1(verify_str.encode("utf-8")).hexdigest()
    # 将鉴权所需参数返回给前端
    return jsonify(
        {
            "appid": APP_ID,
            "signature": signature,
            "noncestr": NONCE_STR,
            "timestamp": timestamp,
        }
    )
```

其中你需要注意，在 server.py 文件中，需通过 .env 文件加载环境变量参数。

```Python
# 从 .env 文件加载环境变量参数
load_dotenv(find_dotenv())

...

# 获取环境变量
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
FEISHU_HOST = os.getenv("FEISHU_HOST")    
```

.env 文件路径：web_app_with_jssdk/python/.env。在启动服务时，需要填写应用真实的 APP_ID、APP_SECRET。

```
APP_ID=cli_9fxxxx00b
APP_SECRET=EX6xxxxOF
FEISHU_HOST=https://open.feishu.cn    # 固定取值。
```

### 前端（客户端）代码

前端利用服务端传来的数据实现 JSAPI 鉴权，鉴权成功后即可进行 JSAPI 的调用。

1. 引入 JSSDK。

JSSDK 为网页应用提供了调用手机系统功能和飞书客户端功能（如：扫一扫、云文档）的能力，并支持性能优化，使你的网页应用体验能够接近原生体验。
- 在需要调用 JSAPI 的页面中，引入 JS 文件，更多信息参见[开发网页应用简介](https://open.feishu.cn/document/uYjL24iN/uMTMuMTMuMTM/introduction)。
- 只有在飞书应用内打开当前网页应用，才会注入全局变量。在其他应用（比如外部浏览器网页）内打开则不会注入。因此，开发者的网页仅可在飞书应用内成功调用 JSAPI。
- 你需要将调用 JSAPI 的页面所在的 `域名:端口号`，配置在 [开发者后台](https://open.feishu.cn/app) > 应用详情页 > 安全设置 > H5 可信
域名中。

示例代码路径：web_app_with_jssdk/python/templates/index.html。在 index.html 文件中，引入 JSSDK。引入后，得到两个全局变量`h5sdk`以及`tt`。目前支持 AMD 或 CMD 引入方式（示例代码为 AMD 引入方式）。

```HTML
<!DOCTYPE html>

<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>网页应用鉴权</title>
    <link rel="stylesheet" href="/public/index.css" />
    <script src="https://cdn.staticfile.org/jquery/1.10.2/jquery.min.js"></script>

<script
      type="text/javascript"
      src="https://lf1-cdn-tos.bytegoofy.com/goofy/lark/op/h5-js-sdk-1.5.16.js"
    ></script>

<script src="https://unpkg.com/vconsole/dist/vconsole.min.js"></script>
    <script>
      var vConsole = new window.VConsole();
    </script>
  </head>

<body>

<script src="/public/index.js"></script>
  </body>
</html>
```

2. 调用 [config](https://open.feishu.cn/document/uYjL24iN/uQjMuQjMuQjM/authentication/h5sdkconfig) 接口进行 JSAPI 鉴权。

前端可利用服务端传来的 appId、timestamp、nonceStr、signature 字段，调用 config 接口进行 JSAPI 鉴权。如果鉴权校验失败，除了可以在 onFail 中进行失败回调的处理，还可以在 h5sdk.error 接口中进行处理（需要在调用 config 接口前完成）。

示例代码路径：web_app_with_jssdk/python/public/index.js。在 index.js 文件中，`apiAuth` 函数中调用 config 接口实现了 JSAPI 的鉴权。

```js
    function apiAuth() {
      console.log("start apiAuth");
      if (!window.h5sdk) {
        console.log("invalid h5sdk");
        alert("please open in feishu");
        return;
      }

// 调用config接口的当前网页url
      // 这里前端一定要用这种方式获取，不建议手写，以免获取到的链接和真实使用的有差距
      const url = encodeURIComponent(location.href.split("#")[0]);
      console.log("接入方前端将需要鉴权的url发给接入方服务端,url为:", url);
      // 向接入方服务端发起请求，获取鉴权参数（appId、timestamp、nonceStr、signature）
      fetch(`/get_config_parameters?url=${url}`)
        .then((response) =>
          response.json().then((res) => {
            console.log(
              "接入方服务端返回给接入方前端的结果(前端调用config接口的所需参数):", res
            );
            // 通过error接口处理API验证失败后的回调
            window.h5sdk.error((err) => {
              throw ("h5sdk error:", JSON.stringify(err));
            });
            // 调用config接口进行鉴权
            window.h5sdk.config({
              appId: res.appid,
              timestamp: res.timestamp,
              nonceStr: res.noncestr,
              signature: res.signature,
              jsApiList: [],
              //鉴权成功回调
              onSuccess: (res) => {
                console.log(`config success: ${JSON.stringify(res)}`);
              },
              //鉴权失败回调
              onFail: (err) => {
                throw `config failed: ${JSON.stringify(err)}`;
              },
            });
            // 完成鉴权后，便可在 window.h5sdk.ready 里调用 JSAPI
            window.h5sdk.ready(() => {
              // window.h5sdk.ready回调函数在环境准备就绪时触发
              // 调用 getUserInfo API 获取已登录用户的基本信息，详细文档参见https://open.feishu.cn/document/uYjL24iN/ucjMx4yNyEjL3ITM
              tt.getUserInfo({
                // getUserInfo API 调用成功回调
                success(res) {
                  console.log(`getUserInfo success: ${JSON.stringify(res)}`);
                  // 单独定义的函数showUser，用于将用户信息展示在前端页面上
                  showUser(res.userInfo);
                },
                // getUserInfo API 调用失败回调
                fail(err) {
                  console.log(`getUserInfo failed:`, JSON.stringify(err));
                },
              });
              // 调用 showToast API 弹出全局提示框，详细文档参见https://open.feishu.cn/document/uAjLw4CM/uYjL24iN/block/api/showtoast
              tt.showToast({
                title: "鉴权成功",
                icon: "success",
                duration: 3000,
                success(res) {
                  console.log("showToast 调用成功", res.errMsg);
                },
                fail(res) {
                  console.log("showToast 调用失败", res.errMsg);
                },
                complete(res) {
                  console.log("showToast 调用结束", res.errMsg);
                },
              });
            });
          })
        )
        .catch(function (e) {
          console.error(e);
        });
    }
    ```

3. 调用 JSAPI。

完成 JSAPI 鉴权后，即可在`window.h5sdk.ready`里调用 JSAPI。示例代码路径：web_app_with_jssdk/python/public/index.js。在`apiAuth`函数中的`window.h5sdk.ready`函数里实现 JSAPI 的调用。
- 出于数据安全考虑，应用需要申请资源访问的权限，并经过开放平台或租户管理员审核后，才可使用对应的开放能力。
<br>
如果你调用的 JSAPI 响应体中某个字段，在对应的开发文档中标注了 **字段权限要求**，表明此字段为敏感字段，仅当应用开通了对应的权限后才会在接口的响应体中返回此字段。如果无需获取这些字段，则不建议申请。权限申请的操作步骤，详情参见[申请 API 权限](https://open.feishu.cn/document/ukTMukTMukTM/uQjN3QjL0YzN04CN2cDN)。

- JSAPI 的调用需要保证在`window.h5sdk.ready`回调函数触发后调用，否则无效。

```js
// 完成鉴权后，便可在 window.h5sdk.ready 里调用 JSAPI
window.h5sdk.ready(() => {
  // window.h5sdk.ready回调函数在环境准备就绪时触发
  // 调用 getUserInfo API 获取已登录用户的基本信息，详细文档参见https://open.feishu.cn/document/uYjL24iN/ucjMx4yNyEjL3ITM
  tt.getUserInfo({
    // getUserInfo API 调用成功回调
    success(res) {
      console.log(`getUserInfo success: ${JSON.stringify(res)}`);
      // 单独定义的函数showUser，用于将用户信息展示在前端页面上
      showUser(res.userInfo);
    },
    // getUserInfo API 调用失败回调
    fail(err) {
      console.log(`getUserInfo failed:`, JSON.stringify(err));
    },
  });
  // 调用 showToast API 弹出全局提示框，详细文档参见https://open.feishu.cn/document/uAjLw4CM/uYjL24iN/block/api/showtoast
  tt.showToast({
    title: "鉴权成功",
    icon: "success",
    duration: 3000,
    success(res) {
      console.log("showToast 调用成功", res.errMsg);
    },
    fail(res) {
      console.log("showToast 调用失败", res.errMsg);
    },
    complete(res) {
      console.log("showToast 调用结束", res.errMsg);
    },
  });
});
```

代码中涉及的 tt 系接口规则如下：

- 所有接口均为异步接口。

- 除了部分特殊接口（例如，[requestAuthCode](https://open.feishu.cn/document/uYjL24iN/uUzMuUzMuUzM/20220308)、[closeWindow](https://open.feishu.cn/document/uYjL24iN/uYTOuYTOuYTO/closewindow)），其他接口均需要鉴权成功后才可以调用。

- 所有接口必须在`window.h5sdk.ready(function(){})`回调函数触发后调用。

- 需输入 object 类型的参数。

- 成功回调 success，失败回调 fail。

```js
  window.tt.方法({
      参数1：'',
      参数2：''，
      success: function(result) {
           // 成功回调     
      },
      fail: function(error) {
           // 失败回调     
        }
  })
  ```

# 相关文档

你可以通过阅读以下内容，了解更多关于网页应用的信息。

- [客户端网页应用简介](https://open.feishu.cn/document/uYjL24iN/uMTMuMTMuMTM/introduction)
- [H5 JSAPI 总览](https://open.feishu.cn/document/uYjL24iN/uMTMuMTMuMTM/)