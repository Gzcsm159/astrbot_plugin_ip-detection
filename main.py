from astrbot.api.all import *
from astrbot.api.event.filter import command, permission_type
from astrbot.api.event import PermissionType  # 权限类型导入
import psutil
import socket
import asyncio
from datetime import datetime

@register("ip_monitor", "TechQuery", "IP监控插件", "1.0.1", "https://your.repo")
class IPMonitor(Star):
    def init(self, context: Context, config: dict):
        super().init(context, config)
        self.last_ips = {"v4": [], "v6": []}
        self.monitor_task = None
        self._init_monitor()

    def _init_monitor(self):
        """安全启动监控任务"""
        if not self.monitor_task or self.monitor_task.done():
            self.monitor_task = asyncio.create_task(self._safe_monitor())

    def _get_network_ips(self):
        """优化IP获取逻辑"""
        ip_dict = {"v4": set(), "v6": set()}
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                    ip_dict["v4"].add(addr.address)
                elif addr.family == socket.AF_INET6 and not addr.address.startswith('::1'):
                    clean_addr = addr.address.split('%')[0]
                    ip_dict["v6"].add(clean_addr)
        return ip_dict

    async def _safe_monitor(self):
        """带异常恢复的监控循环"""
        while True:
            try:
                await self.ip_change_monitor()
            except Exception as e:
                print(f"[ERROR] 监控异常: {str(e)}")
                await asyncio.sleep(300)

    async def ip_change_monitor(self):
        """IP变更监控核心逻辑"""
        await asyncio.sleep(30)
        
        while True:
            current_ips = self._get_network_ips()
            changes = {}
            
            for ip_type in ["v4", "v6"]:
                last = set(self.last_ips.get(ip_type, []))
                curr = current_ips[ip_type]
                
                if last != curr:
                    changes[ip_type] = {
                        "added": list(curr - last),
                        "removed": list(last - curr)
                    }
            
            if changes and self.config.get("notify_target"):
                await self._send_ip_change_notification(changes)
                self.last_ips = current_ips
                
            await asyncio.sleep(600)

    async def _send_ip_change_notification(self, changes: dict):
        """构造通知消息"""
        msg = (MessageChain()
            .message("🌐 网络地址变更告警\n")
            .text(f"🕒 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"))
        
        for ip_type, diff in changes.items():
            msg = (msg
                .message(f"IPv{ip_type[-1]}变动：\n")
                .message(f"➕ 新增: {', '.join(diff['added']) or '无'}\n")
                .message(f"➖ 移除: {', '.join(diff['removed']) or '无'}\n\n"))
        
        try:
            await self.context.send_message(
                unified_msg_origin=self.config["notify_target"],
                message=msg
            )
        except Exception as e:
            print(f"通知发送失败: {str(e)}")

    @command("set_notify")
    @permission_type(PermissionType.ADMIN)
    async def set_notify_channel(self, event: AstrMessageEvent):
        """设置通知频道"""
        self.config["notify_target"] = event.unified_msg_origin
        self.config.save_config()
        
        response = (event.make_result()
            .message("✅ 通知设置已更新\n")
            .message(f"🔔 目标类型: {'群组' if event.is_group_message() else '私聊'}\n")
            .message(f"📡 平台: {event.get_platform_name().upper()}"))
        
        yield response

    @command("sysinfo")
    async def get_system_info(self, event: AstrMessageEvent):
        """获取系统信息"""
        current_ips = self._get_network_ips()
        
        info = (event.make_result()
            .message("🖥️ 系统状态监控\n")
            .text(f"IPv4: {', '.join(current_ips['v4']) or '无'}\n")
            .text(f"IPv6: {', '.join(current_ips['v6']) or '无'}\n")
            .text(f"CPU使用率: {psutil.cpu_percent()}%\n")
            .text(f"内存使用: {psutil.virtual_memory().percent}%"))
        
        yield info
