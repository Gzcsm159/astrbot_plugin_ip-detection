# 必须的导入项
from astrbot.api.all import *
from astrbot.api.event.filter import permission_type, PermissionType
import psutil
import socket
import asyncio
from datetime import datetime

@register("ip_monitor", "YourName", "IP地址监控插件", "1.0.0", "https://your.repo.url")
class IPMonitor(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 初始化存储
        self.last_ipv4 = []
        self.last_ipv6 = []
        self.notify_target = None  # 存储通知目标信息
        # 启动监控任务
        asyncio.create_task(self.ip_change_monitor())

    def _get_network_ips(self):
        """获取当前所有网络接口IP"""
        addrs = psutil.net_if_addrs()
        ipv4_list = []
        ipv6_list = []
        
        for iface, snics in addrs.items():
            for snic in snics:
                # 处理IPv4
                if snic.family == socket.AF_INET and snic.address != '127.0.0.1':
                    ipv4_list.append(snic.address)
                # 处理IPv6
                elif snic.family == socket.AF_INET6:
                    addr = snic.address.split('%')[0]
                    if addr != '::1':
                        ipv6_list.append(addr)
        return sorted(ipv4_list), sorted(ipv6_list)

    async def ip_change_monitor(self):
        """IP变化监控后台任务"""
        await asyncio.sleep(10)  # 初始延迟
        
        while True:
            try:
                current_v4, current_v6 = self._get_network_ips()
                
                # 检测变化
                v4_changed = current_v4 != self.last_ipv4
                v6_changed = current_v6 != self.last_ipv6
                
                # 如果有变化且设置了通知目标
                if (v4_changed or v6_changed) and self.notify_target:
                    # 构建消息链
                    msg_chain = MessageChain()
                    msg_chain.append(Plain("🛜 检测到IP地址变化\n"))
                    
                    if v4_changed:
                        msg_chain.append(Plain(
                            f"IPv4: {', '.join(self.last_ipv4) or '无'} → {', '.join(current_v4)}\n"
                        ))
                    if v6_changed:
                        msg_chain.append(Plain(
                            f"IPv6: {', '.join(self.last_ipv6) or '无'} → {', '.join(current_v6)}\n"
                        ))
                    
                    msg_chain.append(Plain(
                        f"⏰ 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    ))
                    
                    # 发送通知
                    await self.context.send_message(
                        unified_msg_origin=self.notify_target["origin"],
                        chain=msg_chain
                    )
                    
                    # 更新记录
                    self.last_ipv4 = current_v4
                    self.last_ipv6 = current_v6
                
                # 首次运行初始化
                elif not self.last_ipv4:
                    self.last_ipv4 = current_v4
                    self.last_ipv6 = current_v6
                
                await asyncio.sleep(600)  # 10分钟检测间隔
                
            except Exception as e:
                print(f"[IP监控] 任务出错: {str(e)}")
                await asyncio.sleep(60)  # 错误后等待1分钟

    @filter.command("set_notify")
    @permission_type(PermissionType.ADMIN)
    async def set_notify_channel(self, event: AstrMessageEvent):
        """设置通知频道（需要管理员权限）"""
        # 存储通知目标信息
        self.notify_target = {
            "origin": event.unified_msg_origin,
            "chat_id": event.chat_id
        }
        
        # 构建确认消息
        confirm_msg = MessageChain()
        confirm_msg.append(Plain("✅ 通知频道设置成功！\n"))
        confirm_msg.append(Plain(f"频道ID: {event.chat_id}"))
        
        yield event.chain_result(confirm_msg)

    @filter.command("sysinfo")
    async def get_system_info(self, event: AstrMessageEvent):
        """获取当前系统信息"""
        current_v4, current_v6 = self._get_network_ips()
        
        # 获取系统指标
        cpu_usage = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 构建消息链
        info_chain = MessageChain()
        info_chain.append(Plain("🖥️ 系统状态监控\n"))
        info_chain.append(Plain(f"IPv4: {', '.join(current_v4) or '无'}\n"))
        info_chain.append(Plain(f"IPv6: {', '.join(current_v6) or '无'}\n"))
        info_chain.append(Plain(f"CPU使用率: {cpu_usage}%\n"))
        info_chain.append(Plain(f"内存使用: {mem.percent}%\n"))
        info_chain.append(Plain(f"磁盘使用: {disk.percent}%"))
        
        # 添加通知状态
        if self.notify_target:
            info_chain.append(Plain("\n\n🔔 通知频道: 已启用"))
        else:
            info_chain.append(Plain("\n\n🔕 通知频道: 未设置"))

        yield event.chain_result(info_chain)

    @filter.command("test_notify")
    @permission_type(PermissionType.ADMIN)
    async def test_notification(self, event: AstrMessageEvent):
        """测试通知功能（需要管理员权限）"""
        if not self.notify_target:
            yield event.plain_result("❌ 尚未设置通知频道")
            return
        
        # 构建测试消息
        test_chain = MessageChain()
        test_chain.append(Plain("🔔 测试通知\n"))
        test_chain.append(Plain("✅ 通知系统工作正常！"))
        
        # 发送测试消息
        await self.context.send_message(
            unified_msg_origin=self.notify_target["origin"],
            chain=test_chain
        )
        
        yield event.plain_result("测试通知已发送")
