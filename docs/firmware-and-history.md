# 固件入口与研究经过

## 适用指纹

- 原厂 OTA 镜像：13,289,255 字节，SHA-256 `3da7a30e60375cd56f7f927495fa014db5b89bcdbf263469aafdf06280da290e`。
- 原厂 `/app/bin/main_app`：`fc3c9deac86625fedb208375cd6d927d8df42bf92e4fcf2115a27cee276022df`。
- 成功安装的 `/app/bootapp`：`835a7e82fb0be2793f45986b5db2cb6bbb160279c941f863c3e1683bb5318c44`。

原厂来源见 `upstream.json`。下载后先校验，不满足指纹即停止；工具中使用断言核验格式，不能以 `python -O` 运行。

## 离线构建

`tools/build_card_hook_candidate.py` 读取原厂升级容器与提取的原始 bootapp，只修改应用文件系统中的 bootapp，追加后台等待存储卡并执行扩展的入口。保留原启动逻辑、模型 D147、启动参数、启动命令与 config 内容。252 个普通文件中仅 bootapp 改变，链接元数据保留。

```sh
python3 tools/extract_container.py downloads/S36_4K.sw build/stock-container
python3 tools/extract_jffs2_readonly.py \
  build/stock-container/appfs.jffs2 private/extracted-appfs
python3 tools/build_card_hook_candidate.py \
  downloads/S36_4K.sw \
  private/extracted-appfs/bootapp \
  build/card-hook
```

参数均为本地文件。输出包含应用分区候选、原厂应用分区恢复候选及清单；工具本身不操作记录仪。`extract_jffs2_readonly.py` 用于 JFFS2 静态提取，链接和设备节点只记录；其他 ARM 工具只读分析程序。

已走通的按键更新使用 `build/stock-container/config` 和新生成的 `build/card-hook/appfs.jffs2`。不要把整个提取目录复制到存储卡，否则会带入本次无意更新的其他分区。生成候选不等于已授权或执行刷写，安装前应逐项确认当前设备身份与备份。

## 实际走通的路径

1. 最初用手机 USB 调试中转连接设备热点，验证设备网络接口；最终没有保留手机依赖。
2. 普通开机没有触发候选整包升级。后续从同一候选中取出根目录 `config`（515 字节）与 `appfs.jffs2`（4,526,204 字节），没有提供其他分区。
3. 按住 OK 供电触发更新路径。屏幕曾保持黑屏后进入系统，最终以 bootapp 读回哈希与 root 诊断确认成功，未把屏幕现象当成成功证据。
4. 成功后清理卡根目录升级文件。日常供电不按 OK；仅更新卡上扩展即可调整联网、SSH、传输逻辑。
5. 增加 Wi-Fi 客户端、DHCP、Dropbear、主码流 RAM 修正，完成正常启动验证。
6. 增加独立只读 HTTP 服务，提供原片清单与下载；验证音频轨道和副码流。
7. 出现 FAT 与启动文件簇链异常后，统一改为电脑 USB 存储维护，诊断全部迁入 RAM。最终正常启动与新原片转存验证通过。

这次按键更新成功一次，不证明其他固件可用。没有导出 U-Boot 做逐字节核对，普通升级不触发的原因尚未确定；恢复候选没有实际刷回验证，不能保证失败后免拆机恢复。

移除卡上根启用标记可按启动逻辑跳过扩展，但不会还原内部 bootapp 字节；格式化卡会删除扩展，内部已导入的 Wi-Fi 配置和 SSH 主机密钥可能仍保留。
