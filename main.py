import logging
from logging.handlers import RotatingFileHandler
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from mirror.backend import DATA
from mirror.window import MainWindow


def main():
    handler = RotatingFileHandler(DATA / "mirror.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("MirrorStage")
    app.setOrganizationName("MirrorStage")
    app.setStyle("Fusion")
    # One owner per desktop session prevents competing capture services.
    socket = QLocalSocket()
    socket.connectToServer("MirrorStage.Desktop")
    if socket.waitForConnected(300):
        socket.write(b"show")
        socket.waitForBytesWritten(300)
        return 0
    server = QLocalServer()
    server.removeServer("MirrorStage.Desktop")
    if not server.listen("MirrorStage.Desktop"):
        raise RuntimeError(server.errorString())
    window = MainWindow()
    def activate():
        client = server.nextPendingConnection()
        client.close()
        client.deleteLater()
        window.show()
        window.raise_()
        window.activateWindow()
    server.newConnection.connect(activate)
    window.show()
    logging.info("Application ready: %s, frozen=%s", window.windowTitle(), getattr(sys, "frozen", False))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
