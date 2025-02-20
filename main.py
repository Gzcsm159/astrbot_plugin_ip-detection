# main.py
from astrbot.api.all import *
from astrbot.api.event.filter import command, permission_type
import psutil
import socket
import asyncio
from datetime import datetime

@register("ip_monitor", "TechQuery", "IP监控插件", "1.1.0", "https://github.com/yourrepo")
class IPMonitor(Star):
    def init(self, context: Context, config: dict):
        super().init(context, config)
        self.last_ips = {"v4": set(), "v6": set()}
        self.monitor_task = None
        self._init_monitor()

    def _init_monitor(self):
        """安全启动监控任务"""
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
        self.monitor_task = asyncio.create_task(self._safe_monitor())

    def _get_network_ips(self):
        """获取有效IP地址"""
        ip_info = {"v4": set(), "v6": set()}
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                # 过滤本地回环和虚拟接口
                if addr.family == socket.AF_INET:
                    if not addr.address.startswith('127.') and not iface.startswith('vEthernet'):
                        ip_info["v4"].add(addr.address)
                elif addr.family == socket.AF_INET6:
                    clean_addr = addr.address.split('%')[0]
                    if not clean_addr.startswith(('fe80', '::1')):
                        ip_info["v6"].add(clean_addr)
        return ip_info

    async def _safe_monitor(self):
        """带错误恢复的监控循环"""
        while True:
            try:
                await self._monitor_loop()
            except Exception as e:
                print(f"[监控异常] {str(e)}")
                await asyncio.sleep(60)

    async def _monitor_loop(self):
        """监控主循环"""
        await asyncio.sleep(10)  # 初始延迟
        while True:
            current_ips = self._get_network_ips()
            changes = self._detect_changes(current_ips)
            
            if changes and self.config.get("notify_target"):
                await self._send_alert(changes)
                self.last_ips = current_ips
                
            await asyncio.sleep(300)  # 5分钟检测间隔

    def _detect_changes(self, current_ips):
        """检测IP变化"""
        changes = {}
        for ip_type in ["v4", "v6"]:
            old = self.last_ips.get(ip_type, set())
            new = current_ips.get(ip_type, set())
            
            added = new - old
            removed = old - new
            
            if added or removed:
                changes[ip_type] = {
                    "added": list(added),
                    "removed": list(removed)
                }
        return changes

    async def _send_alert(self, changes):
        """发送变更通知"""
        msg = (MessageChain()
            .message("🛜 网络地址变化告警\n")
            .text(f"⏰ 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"))
        
        for ip_type, diff in changes.items():
            version = "IPv4" if ip_type == "v4" else "IPv6"
            msg.message(f"{version}变动：\n")
            if diff["added"]:
                msg.message(f"➕ 新增: {', '.join(diff['added'])}\n")
            if diff["removed"]:
                msg.message(f"➖ 移除: {', '.join(diff['removed'])}\n")
        
        try:
            await self.context.send_message(
                unified_msg_origin=self.config["notify_target"],
                message=msg
            )
        except Exception as e:
            print(f"[通知发送失败] {str(e)}")

    @command("set_notify")
    @permission_type("admin")
    async def set_notify_channel(self, event: AstrMessageEvent):
        """设置通知频道"""
        self.config["notify_target"] = event.unified_msg_origin
        self.config.save_config()
        
        platform = event.get_platform_name().upper()
        target_type = "群组" if event.is_group_message() else "私聊"
        
        yield event.plain_result(
            f"✅ 通知频道已设置为\n"
            f"平台: {platform}\n"
            f"类型: {target_type}\n"
            f"ID: {event.get_group_id() or event.get_sender_id()}"
        )

    @command("netstat")
    async def get_network_status(self, event: AstrMessageEvent):
        """获取当前网络状态"""
        ips = self._get_network_ips()
        msg = (MessageChain()
            .message("🌐 实时网络状态\n")
            .message(f"IPv4: {', '.join(ips['v4']) or '无'}\n")
            .message(f"IPv6: {', '.join(ips['v6']) or '无'}\n")
            .message(f"⏱ 最后检测: {datetime.now().strftime('%H:%M:%S')}"))
        
        yield msg

    @command("monitor_control")
    @permission_type("admin")
    async def control_monitor(self, event: AstrMessageEvent, action: str = "status"):
        """监控任务管理"""
        action = action.lower()
        if action == "stop":
            if self.monitor_task:
                self.monitor_task.cancel()
                yield event.plain_result("🛑 监控任务已停止")
            else:
                yield event.plain_result("⚠️ 监控任务未运行")
        elif action == "start":
            self._init_monitor()
            yield event.plain_result("✅ 监控任务已启动")
        else:
            status = "运行中" if self.monitor_task and not self.monitor_task.done() else "已停止"
            yield event.plain_result(f"📊 监控任务状态: {status}")
