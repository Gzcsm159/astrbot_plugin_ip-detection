# 导入必要的库
from astrbot.api.all import *          # 导入AstrBot核心API
from astrbot.api.event.filter import command, permission_type, PermissionType
import psutil       # 用于获取系统信息
import socket       # 用于获取网络信息
import asyncio      # 异步任务支持
from datetime import datetime  # 时间处理

@register("ip_monitor", "YourName", "IP地址监控插件", "1.0.0", "https://your.repo.url")
class IPMonitor(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 初始化存储变量
        self.last_ipv4 = []    # 存储上次IPv4地址
        self.last_ipv6 = []    # 存储上次IPv6地址
        self.notify_target = None  # 存储通知目标标识
        # 启动后台监控任务
        asyncio.create_task(self.ip_change_monitor())

    def _get_network_ips(self):
        """获取当前所有网络接口的IP地址"""
        addrs = psutil.net_if_addrs()
        ipv4_list = []
        ipv6_list = []
        
        # 遍历网络接口
        for iface, snics in addrs.items():
            for snic in snics:
                # 过滤本地回环地址
                if snic.family == socket.AF_INET and snic.address != '127.0.0.1':
                    ipv4_list.append(snic.address)
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
                # 获取当前IP地址
                current_v4, current_v6 = self._get_network_ips()
                
                # 检测变化
                v4_changed = current_v4 != self.last_ipv4
                v6_changed = current_v6 != self.last_ipv6
                
                # 如果检测到变化且有设置通知目标
                if (v4_changed or v6_changed) and self.notify_target:
                    # 构建消息链
                    message = MessageChain()
                    message.plain("🛜 检测到IP地址变化\n")
                    
                    if v4_changed:
                        message.plain(f"IPv4: {', '.join(self.last_ipv4) or '无'} → {', '.join(current_v4)}\n")
                    
                    if v6_changed:
                        message.plain(f"IPv6: {', '.join(self.last_ipv6) or '无'} → {', '.join(current_v6)}\n")
                    
                    message.plain(f"⏰ 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # 发送通知
                    await self.context.send_message(
                        unified_msg_origin=self.notify_target,
                        message=message
                    )
                    
                    # 更新存储的IP地址
                    self.last_ipv4 = current_v4
                    self.last_ipv6 = current_v6
                
                # 首次运行初始化
                elif not self.last_ipv4:
                    self.last_ipv4 = current_v4
                    self.last_ipv6 = current_v6
                
                await asyncio.sleep(600)  # 每10分钟检查一次
                
            except Exception as e:
                print(f"[IP监控] 任务出错: {str(e)}")
                await asyncio.sleep(60)  # 出错后等待1分钟重试

    @command("set_notify")
    @permission_type(PermissionType.ADMIN)
    async def set_notify_channel(self, event: AstrMessageEvent):
        """设置通知频道（仅管理员）"""
        # 存储统一消息来源标识
        self.notify_target = event.unified_msg_origin
        
        # 构建响应消息
        response = event.make_result()
        response.message("✅ 通知频道设置成功！\n")
        
        # 添加详细信息
        if event.message_type == EventMessageType.GROUP_MESSAGE:
            response.message(f"群组ID: {event.group_id}\n")
        else:
            response.message(f"用户ID: {event.get_sender_id()}\n")
        
        response.message(f"平台类型: {event.get_platform_name()}")
        
        yield response

    @command("sysinfo")
    async def get_system_info(self, event: AstrMessageEvent):
        """获取系统信息"""
        current_v4, current_v6 = self._get_network_ips()
        
        # 获取系统指标
        cpu_usage = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 构建消息
        info = event.make_result()
        info.message("🖥️ 系统状态监控\n")
        info.message(f"IPv4: {', '.join(current_v4) or '无'}\n")
        info.message(f"IPv6: {', '.join(current_v6) or '无'}\n")
        info.message(f"CPU使用率: {cpu_usage}%\n")
        info.message(f"内存使用: {mem.percent}%\n")
        info.message(f"磁盘使用: {disk.percent}%")
        
        # 添加通知状态
        if self.notify_target:
            info.message("\n\n🔔 通知频道: 已启用")
        else:
            info.message("\n\n🔕 通知频道: 未设置")

        yield info

    @command("test_notify")
    @permission_type(PermissionType.ADMIN)
    async def test_notification(self, event: AstrMessageEvent):
        """测试通知功能（仅管理员）"""
        if not self.notify_target:
            yield event.plain_result("❌ 尚未设置通知频道")
            return
        
        try:
            # 构建测试消息
            test_msg = MessageChain()
            test_msg.plain("🔔 测试通知\n")
            test_msg.plain("✅ 通知系统工作正常！")
            
            # 发送通知
            await self.context.send_message(
                unified_msg_origin=self.notify_target,
                message=test_msg
            )
            yield event.plain_result("测试通知已发送")
        except Exception as e:
            yield event.plain_result(f"❌ 通知发送失败: {str(e)}")
