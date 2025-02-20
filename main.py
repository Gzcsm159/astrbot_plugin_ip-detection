from astrbot.api.all import *
from astrbot.api.event.filter import command
import psutil
import socket
import asyncio
from datetime import datetime

@register("ip_monitor", "TechQuery", "IP监控插件", "1.0.3", "https://your.repo")
class IPMonitor(Star):
    def init(self, context: Context, config: dict):
        super().init(context, config)
        self.last_ips = {"v4": set(), "v6": set()}
        self._init_monitor()

    def _init_monitor(self):
        """监控任务初始化"""
        if not hasattr(self, 'monitor_task') or self.monitor_task.done():
            self.monitor_task = asyncio.create_task(self._safe_monitor())

    def _get_network_ips(self):
        """获取网络接口IP信息"""
        ip_info = {"v4": set(), "v6": set()}
        for interface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                    ip_info["v4"].add(addr.address)
                elif addr.family == socket.AF_INET6:
                    clean_addr = addr.address.split('%')[0]
                    if not clean_addr.startswith('fe80') and not clean_addr == '::1':
                        ip_info["v6"].add(clean_addr)
        return ip_info

    async def _safe_monitor(self):
        """带错误恢复的监控循环"""
        while True:
            try:
                await self._ip_monitor_loop()
            except Exception as e:
                print(f"[MONITOR ERROR] {str(e)}")
                await asyncio.sleep(60)

    async def _ip_monitor_loop(self):
        """IP监控主循环"""
        await asyncio.sleep(10)  # 初始延迟
        
        while True:
            current_ips = self._get_network_ips()
            changes = self._detect_ip_changes(current_ips)
            
            if changes and self.config.get("notify_target"):
                await self._send_notification(changes)
                self.last_ips = current_ips
                
            await asyncio.sleep(300)  # 5分钟检测间隔

    def _detect_ip_changes(self, current: dict) -> dict:
        """检测IP变化"""
        changes = {}
        for ip_type in ["v4", "v6"]:
            prev = self.last_ips.get(ip_type, set())
            curr = current.get(ip_type, set())
            
            added = curr - prev
            removed = prev - curr
            
            if added or removed:
                changes[ip_type] = {
                    "added": list(added),
                    "removed": list(removed)
                }
        return changes

    async def _send_notification(self, changes: dict):
        """发送平台兼容通知"""
        msg = (MessageChain()
            .message("🛜 网络地址变化告警\n")
            .text(f"⏰ 时间: {datetime.now().strftime('%m-%d %H:%M')}\n"))
        
        for ip_type, diff in changes.items():
            version = "IPv4" if ip_type == "v4" else "IPv6"
            msg.message(f"{version}变化：\n")
            if diff["added"]:
                # 修正点：补全join()闭合括号
                msg.message(f"➕ 新增: {', '.join(diff['added'])}\n")  # <-- 这里修复
            if diff["removed"]:
                # 修正点：补全join()闭合括号
                msg.message(f"➖ 移除: {', '.join(diff['removed'])}\n")  # <-- 这里修复
        
        try:
            await self.context.send_message(
                unified_msg_origin=self.config["notify_target"],
                message=msg
            )
        except Exception as e:
            print(f"[NOTIFY FAILED] {str(e)}")

    @command("set_notify")
    @permission_type("admin")
    async def set_notify_target(self, event: AstrMessageEvent):
        """设置通知目标"""
        self.config["notify_target"] = event.unified_msg_origin
        self.config.save_config()
        
        yield event.plain_result(
            f"✅ 通知目标已设置为 {event.get_platform_name()} 平台的"
            f"{'群组' if event.is_group_message() else '私聊'}会话"
        )

    @command("network_info")
    async def get_network_info(self, event: AstrMessageEvent):
        """获取网络信息"""
        ips = self._get_network_ips()
        msg = (MessageChain()
            .message("🌐 当前网络状态\n")
            .message(f"IPv4: {', '.join(ips['v4']) or '无'}\n")  # <-- 检查这里
            .message(f"IPv6: {', '.join(ips['v6']) or '无'}"))  # <-- 检查这里
        
        yield msg
