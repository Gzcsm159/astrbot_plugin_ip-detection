# main.py
from astrbot.api.all import *
from astrbot.api.event.filter import command, permission_type
import psutil
import socket
import asyncio
from datetime import datetime

@register("ip_monitor", "TechQuery", "IP监控插件", "1.3.0", "https://github.com/yourrepo")
class IPMonitor(Star):
    def init(self, context: Context, config: dict):
        # 配置系统三重保障初始化
        super().init(context, config or {})  # 处理空配置
        self.context = context
        self.config = getattr(self, 'config', {})  # 防御性初始化
        self.config.update(config if isinstance(config, dict) else {})
        self.config.setdefault("notify_target", "")
        
        # 网络状态跟踪
        self.last_ips = {"v4": set(), "v6": set()}
        self.monitor_task = None
        self._init_monitor()

    def _init_monitor(self):
        """安全初始化监控任务"""
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
        self.monitor_task = asyncio.create_task(self._monitor_service())

    def _get_valid_ips(self):
        """获取有效IP地址（增强过滤）"""
        ip_info = {"v4": set(), "v6": set()}
        for iface, addrs in psutil.net_if_addrs().items():
            # 过滤虚拟接口
            if "virtual" in iface.lower() or "vEthernet" in iface:
                continue
                
            for addr in addrs:
                # IPv4处理
                if addr.family == socket.AF_INET:
                    if (not addr.address.startswith('127.') 
                       and (addr.netmask not in ['255.255.255.255', '0.0.0.0']):
                        ip_info["v4"].add(addr.address)
                # IPv6处理        
                elif addr.family == socket.AF_INET6:
                    clean_addr = addr.address.split('%')[0]
                    if (not clean_addr.startswith(('fe80', '::1'))) 
                       and (clean_addr.count(':') > 2):
                        ip_info["v6"].add(clean_addr)
        return ip_info

    async def _monitor_service(self):
        """监控服务（带双保险机制）"""
        while True:
            try:
                await self._monitor_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[MONITOR CRASH] {str(e)}")
                await asyncio.sleep(60)

    async def _monitor_cycle(self):
        """监控周期逻辑"""
        await asyncio.sleep(10)  # 初始延迟
        
        while True:
            current_ips = self._get_valid_ips()
            changes = self._detect_changes(current_ips)
            
            if changes and self.config.get("notify_target"):
                await self._send_notice(changes)
                self.last_ips = current_ips
                
            await asyncio.sleep(300)

    def _detect_changes(self, current):
        """变更检测（支持回滚）"""
        changes = {}
        for ip_type in ["v4", "v6"]:
            old = self.last_ips.get(ip_type, set())
            new = current.get(ip_type, set())
            
            added = new - old
            removed = old - new
            
            if added or removed:
                changes[ip_type] = {
                    "added": sorted(added),
                    "removed": sorted(removed),
                    "timestamp": datetime.now().isoformat()
                }
        return changes

    async def _send_notice(self, changes):
        """发送平台适配通知"""
        try:
            msg = self._build_notice_message(changes)
            await self.context.send_message(
                unified_msg_origin=self.config["notify_target"],
                message=msg
            )
        except Exception as e:
            print(f"[NOTICE FAILED] {str(e)}")
            # 失败重试逻辑
            await asyncio.sleep(5)
            await self._send_notice(changes)

    def _build_notice_message(self, changes):
        """构建跨平台消息"""
        msg = (MessageChain()
            .message("🔔 网络地址变化通知\n")
            .text(f"⏱ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"))
        
        for ip_type, detail in changes.items():
            version = "IPv4" if ip_type == "v4" else "IPv6"
            msg.message(f"【{version}变更】\n")
            if detail["added"]:
                msg.message(f"➕ 新增: {', '.join(detail['added'])}\n")
            if detail["removed"]:
                msg.message(f"➖ 移除: {', '.join(detail['removed'])}\n")
        
        # 平台适配增强
        if "qq" in self.config.get("notify_target", ""):
            msg = msg.face(112)  # QQ笑脸表情
        elif "wechat" in self.config.get("notify_target", ""):
            msg = msg.image("https://example.com/wechat-alert.png")
        
        return msg

    @command("set_notify")
    @permission_type("admin")
    async def set_notify_channel(self, event: AstrMessageEvent):
        """设置通知频道（五重保障）"""
        # 配置系统保障
        if not hasattr(self, 'config'):
            self.config = {}
        if not isinstance(self.config, dict):
            self.config = {}
        self.config.setdefault("notify_target", "")
        
        # 保存配置
        self.config["notify_target"] = event.unified_msg_origin
        try:
            await self.context.config_manager.save_config(
                plugin_name=self.name,
                config=self.config
            )
        except Exception as e:
            yield event.plain_result(f"❌ 配置保存失败: {str(e)}")
            return
        
        # 构建响应
        response = (MessageChain()
            .message("✅ 通知设置成功\n")
            .message(f"▪ 平台: {event.get_platform_name().upper()}\n")
            .message(f"▪ 类型: {'群组' if event.is_group_message() else '私聊'}\n")
            .message(f"▪ 会话ID: {event.get_group_id() or event.get_sender_id()}"))
        
        yield response

    @command("netstat")
    async def show_network_status(self, event: AstrMessageEvent):
        """显示网络状态"""
        ips = self._get_valid_ips()
        msg = (MessageChain()
            .message("🌐 实时网络状态\n")
            .message(f"🕒 检测时间: {datetime.now().strftime('%H:%M:%S')}\n")
            .message(f"📡 IPv4地址:\n{', '.join(ips['v4']) or '无'}\n")
            .message(f"📡 IPv6地址:\n{', '.join(ips['v6']) or '无'}"))
        
        yield msg

    @command("monitor")
    @permission_type("admin")
    async def manage_monitor(self, event: AstrMessageEvent, action: str = "status"):
        """监控任务管理"""
        action = action.lower()
        status_map = {
            "running": "🟢 运行中",
            "stopped": "🔴 已停止"
        }
        
        current_status = "running" if self.monitor_task and not self.monitor_task.done() else "stopped"
        
        if action == "stop":
            if current_status == "running":
                self.monitor_task.cancel()
                yield event.plain_result("🛑 已停止监控")
            else:
                yield event.plain_result("ℹ️ 监控未运行")
        elif action == "start":
            if current_status == "stopped":
                self._init_monitor()
                yield event.plain_result("✅ 已启动监控")
            else:
                yield event.plain_result("ℹ️ 监控已在运行")
        elif action == "restart":
            self._init_monitor()
            yield event.plain_result("🔄 已重启监控")
        else:
            yield event.plain_result(f"📊 当前状态: {status_map[current_status]}")
