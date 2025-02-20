from astrbot.api.all import *
from astrbot.api.event.filter import command, permission_type, PermissionType
import psutil
import socket
import asyncio
from datetime import datetime

@register("ip_monitor", "YourName", "IP地址监控插件", "1.0.0", "https://your.repo.url")
class IPMonitor(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.last_ipv4 = []
        self.last_ipv6 = []
        self.notify_origin = None
        asyncio.create_task(self.ip_change_monitor())

    def _get_network_ips(self):
        """获取当前所有网络接口IP"""
        addrs = psutil.net_if_addrs()
        ipv4_list = []
        ipv6_list = []
        
        for iface, snics in addrs.items():
            for snic in snics:
                if snic.family == socket.AF_INET and snic.address != '127.0.0.1':
                    ipv4_list.append(snic.address)
                elif snic.family == socket.AF_INET6:
                    addr = snic.address.split('%')[0]
                    if addr != '::1':
                        ipv6_list.append(addr)
        return sorted(ipv4_list), sorted(ipv6_list)

    async def ip_change_monitor(self):
        """IP变化监控后台任务"""
        await asyncio.sleep(10)
        
        while True:
            try:
                current_v4, current_v6 = self._get_network_ips()
                
                v4_changed = current_v4 != self.last_ipv4
                v6_changed = current_v6 != self.last_ipv6
                
                if (v4_changed or v6_changed) and self.notify_origin:
                    msg_parts = [
                        Plain("🛜 检测到IP地址变化\n")
                    ]
                    
                    if v4_changed:
                        msg_parts.append(Plain(
                            f"IPv4: {', '.join(self.last_ipv4) or '无'} → {', '.join(current_v4)}\n"
                        ))
                    if v6_changed:
                        msg_parts.append(Plain(
                            f"IPv6: {', '.join(self.last_ipv6) or '无'} → {', '.join(current_v6)}\n"
                        ))
                    
                    msg_parts.append(Plain(
                        f"⏰ 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    ))
                    
                    await self.context.send_message(
                        unified_msg_origin=self.notify_origin,
                        chain=MessageChain(msg_parts)
                    )
                    
                    self.last_ipv4 = current_v4
                    self.last_ipv6 = current_v6
                
                elif not self.last_ipv4:
                    self.last_ipv4 = current_v4
                    self.last_ipv6 = current_v6
                
                await asyncio.sleep(600)
                
            except Exception as e:
                print(f"[IP监控] 任务出错: {str(e)}")
                await asyncio.sleep(60)

    @command("set_notify")
    @permission_type(PermissionType.ADMIN)
    async def set_notify_channel(self, event: AstrMessageEvent):
        """设置通知频道"""
        # 兼容性消息类型判断
        chat_info = "未知频道类型"
        if hasattr(event, 'group_id') and event.group_id:
            chat_info = f"群组ID: {event.group_id}"
        elif hasattr(event, 'user_id') and event.user_id:
            chat_info = f"用户ID: {event.user_id}"
        
        self.notify_origin = event.unified_msg_origin
        
        confirm_msg = MessageChain([
            Plain("✅ 通知频道设置成功！\n"),
            Plain(chat_info)
        ])

        yield event.chain_result(confirm_msg)

    @command("sysinfo")
    async def get_system_info(self, event: AstrMessageEvent):
        """获取系统信息"""
        current_v4, current_v6 = self._get_network_ips()
        
        cpu_usage = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        info_parts = [
            Plain("🖥️ 系统状态监控\n"),
            Plain(f"IPv4: {', '.join(current_v4) or '无'}\n"),
            Plain(f"IPv6: {', '.join(current_v6) or '无'}\n"),
            Plain(f"CPU使用率: {cpu_usage}%\n"),
            Plain(f"内存使用: {mem.percent}%\n"),
            Plain(f"磁盘使用: {disk.percent}%"),
            Plain("\n\n🔔 通知频道: 已启用" if self.notify_origin else "\n\n🔕 通知频道: 未设置")
        ]

        yield event.chain_result(MessageChain(info_parts))

    @command("test_notify")
    @permission_type(PermissionType.ADMIN)
    async def test_notification(self, event: AstrMessageEvent):
        """测试通知"""
        if not self.notify_origin:
            yield event.plain_result("❌ 尚未设置通知频道")
            return
        
        test_chain = MessageChain([
            Plain("🔔 测试通知\n"),
            Plain("✅ 通知系统工作正常！")
        ])
        
        await self.context.send_message(
            unified_msg_origin=self.notify_origin,
            chain=test_chain
        )
        
        yield event.plain_result("测试通知已发送")
