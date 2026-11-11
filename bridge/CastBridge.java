import com.huawei.hosscrcpy.api.HosRemoteConfig;
import com.huawei.hosscrcpy.api.HosRemoteDevice;
import com.huawei.hosscrcpy.api.ScreenCapCallback;
import java.io.*;
import java.net.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicBoolean;

/** Single-viewer H.264 transport. The SDK owns device capture and HDC forwarding. */
public final class CastBridge {
    private static final AtomicBoolean stopping = new AtomicBoolean();
    private static HosRemoteDevice device;
    private static Socket viewer;

    private static synchronized void stop() {
        if (!stopping.compareAndSet(false, true)) return;
        try { if (viewer != null) viewer.close(); } catch (IOException ignored) { }
        try { if (device != null) device.stopCaptureScreen(); }
        catch (Exception error) { System.err.println("Capture cleanup: " + error); }
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 6) throw new IllegalArgumentException("serial hdc scale fps bitrate token");
        Runtime.getRuntime().addShutdownHook(new Thread(CastBridge::stop));
        // EOF closes capture even when the desktop process crashes.
        Thread parent = new Thread(() -> {
            try { while (System.in.read() != -1) { } } catch (IOException ignored) { }
            stop();
            System.exit(0);
        }, "parent-lifetime");
        parent.setDaemon(true);
        parent.start();
        HosRemoteConfig config = new HosRemoteConfig(args[0]);
        config.setIp("127.0.0.1");
        String hdcPort = System.getenv("OHOS_HDC_SERVER_PORT");
        if (hdcPort != null && !hdcPort.isEmpty()) config.setHdcPort(hdcPort);
        config.setHdcPath(args[1]);
        config.setScale(Integer.parseInt(args[2]));
        config.setFrameRate(Integer.parseInt(args[3]));
        // HOScrcpy expects MiBit/s and performs the conversion internally.
        config.setBitRate(Integer.parseInt(args[4]));
        config.setIFrameInterval(1000);
        device = new HosRemoteDevice(config);
        if (!device.isOnline()) throw new IOException("Device offline");
        try (ServerSocket server = new ServerSocket(0, 1, InetAddress.getLoopbackAddress())) {
            server.setSoTimeout(30000);
            System.out.println("CAST_READY " + server.getLocalPort());
            System.out.flush();
            viewer = server.accept();
            viewer.setTcpNoDelay(true);
            viewer.setSoTimeout(15000);
            BufferedReader commands = new BufferedReader(new InputStreamReader(viewer.getInputStream(), StandardCharsets.UTF_8));
            if (!args[5].equals(commands.readLine())) throw new IOException("Invalid session token");
            DataOutputStream output = new DataOutputStream(new BufferedOutputStream(viewer.getOutputStream()));
            device.stopCaptureScreen();
            device.startCaptureScreen(new ScreenCapCallback() {
                public void onReady() { System.out.println("CAST_STARTED"); }
                public synchronized void onData(ByteBuffer buffer) {
                    if (stopping.get()) return;
                    byte[] data = new byte[buffer.remaining()];
                    buffer.get(data);
                    try {
                        output.writeInt(data.length);
                        output.write(data);
                        output.flush();
                    } catch (IOException error) {
                        // Close on a separate thread so SDK callback cleanup cannot deadlock.
                        new Thread(() -> { stop(); System.exit(0); }, "capture-close").start();
                    }
                }
                public void onException(Throwable error) {
                    System.err.println("CAST_ERROR " + error);
                    new Thread(() -> { stop(); System.exit(2); }, "capture-error").start();
                }
            });
            try {
                while (!stopping.get()) {
                    String command = commands.readLine();
                    if (command == null || command.equals("stop")) break;
                }
            } catch (SocketException disconnected) {
                // The viewer closes its socket to cancel immediately.
                System.out.println("CAST_DISCONNECTED");
            }
        } finally {
            stop();
        }
        System.exit(0);
    }
}
