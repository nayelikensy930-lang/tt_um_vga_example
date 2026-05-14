# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

import os
import glob
import itertools


@cocotb.test()
async def test_project(dut):
    # Set clock period to 40 ns (25 MHz)
    CLOCK_PERIOD = 40

    # VGA timing parameters matching hvsync_generator.v
    H_DISPLAY = 640
    H_FRONT   =  16
    H_SYNC    =  96
    H_BACK    =  48
    V_DISPLAY = 480
    V_FRONT   =  10
    V_SYNC    =   2
    V_BACK    =  33

    # Number of frames to capture
    CAPTURE_FRAMES = 3

    # Derived constants
    H_SYNC_START = H_DISPLAY + H_FRONT
    H_SYNC_END   = H_SYNC_START + H_SYNC
    H_TOTAL      = H_SYNC_END + H_BACK
    V_SYNC_START = V_DISPLAY + V_FRONT
    V_SYNC_END   = V_SYNC_START + V_SYNC
    V_TOTAL      = V_SYNC_END + V_BACK

    # Palette mapping uo_out values to RGB color
    # uo_out = {hsync, B[0], G[0], R[0], vsync, B[1], G[1], R[1]}
    palette = [bytes(3)] * 256
    for r1, r0, g1, g0, b1, b0 in itertools.product(range(2), repeat=6):
        red   = 170*r1 + 85*r0
        green = 170*g1 + 85*g0
        blue  = 170*b1 + 85*b0
        color_index = b0<<6 | g0<<5 | r0<<4 | b1<<2 | g1<<1 | r1<<0
        for sync_bits in (0x00, 0x08, 0x80, 0x88):
            palette[color_index | sync_bits] = bytes((red, green, blue))

    # Set up the clock
    clock = Clock(dut.clk, CLOCK_PERIOD, unit="ns")
    cocotb.start_soon(clock.start())

    # Reset the design
    dut.ena.value    = 1
    dut.ui_in.value  = 0
    dut.uio_in.value = 0
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value  = 1
    await ClockCycles(dut.clk, 2)

    async def check_line(expected_vsync):
        for i in range(H_TOTAL):
            hsync = int(dut.uo_out.value[7])
            vsync = int(dut.uo_out.value[3])
            assert hsync == (0 if H_SYNC_START <= i < H_SYNC_END else 1), "Unexpected hsync pattern"
            assert vsync == expected_vsync, "Unexpected vsync pattern"
            await ClockCycles(dut.clk, 1)

    async def capture_line(framebuffer, offset):
        for i in range(H_TOTAL):
            hsync = int(dut.uo_out.value[7])
            vsync = int(dut.uo_out.value[3])
            assert hsync == (0 if H_SYNC_START <= i < H_SYNC_END else 1), "Unexpected hsync pattern"
            assert vsync == 1, "Unexpected vsync pattern"
            if i < H_DISPLAY:
                framebuffer[offset+3*i:offset+3*i+3] = palette[int(dut.uo_out.value)]
            await ClockCycles(dut.clk, 1)

    async def capture_frame(frame_num, check_sync=True):
        framebuffer = bytearray(V_DISPLAY * H_DISPLAY * 3)
        for j in range(V_DISPLAY):
            dut._log.info(f"Frame {frame_num}, line {j} (display)")
            await capture_line(framebuffer, 3*j*H_DISPLAY)
        if check_sync:
            for j in range(V_DISPLAY, V_DISPLAY + V_FRONT):
                dut._log.info(f"Frame {frame_num}, line {j} (front porch)")
                await check_line(1)
            for j in range(V_DISPLAY + V_FRONT, V_DISPLAY + V_FRONT + V_SYNC):
                dut._log.info(f"Frame {frame_num}, line {j} (sync pulse)")
                await check_line(0)
            for j in range(V_DISPLAY + V_FRONT + V_SYNC, V_TOTAL):
                dut._log.info(f"Frame {frame_num}, line {j} (back porch)")
                await check_line(1)
        else:
            dut._log.info(f"Frame {frame_num}, skipping non-display lines")
            await ClockCycles(dut.clk, H_TOTAL * (V_TOTAL - V_DISPLAY))

        os.makedirs("output", exist_ok=True)
        with open(f"output/frame{frame_num}.raw", "wb") as f:
            f.write(framebuffer)
        dut._log.info(f"Frame {frame_num} captured and saved as raw RGB data")
        return framebuffer

    os.makedirs("output", exist_ok=True)

    for i in range(CAPTURE_FRAMES):
        framebuffer = await capture_frame(i)
        dut._log.info(f"Frame {i} captured, size: {len(framebuffer)} bytes")


@cocotb.test()
async def compare_reference(dut):
    raw_files = glob.glob("output/frame*.raw")
    assert len(raw_files) > 0, "No frame files were captured"

    for raw_file in raw_files:
        basename = os.path.basename(raw_file)
        dut._log.info(f"Checking {basename}")

        file_size = os.path.getsize(raw_file)
        expected_size = 640 * 480 * 3

        assert file_size == expected_size, f"{basename} has size {file_size}, expected {expected_size}"
        dut._log.info(f"{basename} OK - size: {file_size} bytes")
