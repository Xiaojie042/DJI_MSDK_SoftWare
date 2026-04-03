"""
CRC 校验工具
为 DJI 协议帧提供 CRC-16 校验
"""

import crcmod


# CRC-16/MODBUS 预编译函数
crc16_modbus = crcmod.predefined.mkCrcFun("modbus")

# CRC-16/CCITT 预编译函数 (备用)
crc16_ccitt = crcmod.predefined.mkCrcFun("crc-ccitt-false")


def calc_crc16(data: bytes, algorithm: str = "modbus") -> int:
    """
    计算 CRC-16 校验值

    Args:
        data: 待校验的字节数据
        algorithm: 算法选择 ("modbus" 或 "ccitt")

    Returns:
        CRC-16 校验值 (int)
    """
    if algorithm == "modbus":
        return crc16_modbus(data)
    elif algorithm == "ccitt":
        return crc16_ccitt(data)
    else:
        raise ValueError(f"不支持的 CRC 算法: {algorithm}")


def verify_crc16(data: bytes, expected_crc: int, algorithm: str = "modbus") -> bool:
    """
    验证 CRC-16 校验值

    Args:
        data: 待校验的字节数据
        expected_crc: 期望的 CRC 值
        algorithm: 算法选择

    Returns:
        校验是否通过
    """
    return calc_crc16(data, algorithm) == expected_crc
