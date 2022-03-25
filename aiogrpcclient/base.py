import asyncio
import json

from aiokit import AioThing
from grpc import StatusCode
from grpc.experimental.aio import insecure_channel


def expose(method):
    method._exposable = True
    return method


class BaseGrpcClient(AioThing):
    temporary_errors = (
        StatusCode.CANCELLED,
        StatusCode.UNAVAILABLE,
    )
    stub_clses = {}

    def __init__(
        self,
        endpoint,
        max_retries: int = 2,
        retry_delay: float = 0.5,
        connection_timeout: float = None,
    ):
        super().__init__()
        if endpoint is None:
            raise RuntimeError(f'`endpoint` must be passed for {self.__class__.__name__} constructor')
        config = [
            ('grpc.dns_min_time_between_resolutions_ms', 1000),
            ('grpc.initial_reconnect_backoff_ms', 1000),
            ('grpc.lb_policy_name', 'round_robin'),
            ('grpc.min_reconnect_backoff_ms', 1000),
            ('grpc.max_reconnect_backoff_ms', 2000),
            ('grpc.service_config', json.dumps({'methodConfig': [{
                'name': [{}],
                'retryPolicy': {
                    'maxAttempts': max_retries,
                    'initialBackoff': f'{retry_delay}s',
                    'maxBackoff': f'{retry_delay}s',
                    'backoffMultiplier': 1,
                    'retryableStatusCodes': list(map(lambda x: x.name, self.temporary_errors)),
                }
            }]}))
        ]
        self.connection_timeout = connection_timeout
        self.channel = insecure_channel(endpoint, config)
        self.stubs = {}
        for stub_name, stub_cls in self.stub_clses.items():
            self.stubs[stub_name] = stub_cls(self.channel)

    async def start(self):
        await asyncio.wait_for(self.channel.channel_ready(), timeout=self.connection_timeout)

    async def stop(self):
        await self.channel.close()

    def get_interface(self):
        return {
            method_name.replace('_', '-'): getattr(self, method_name) for method_name in dir(self)
            if callable(getattr(self, method_name)) and getattr(getattr(self, method_name), '_exposable', False)
        }
