#include "mainwindow.h"
#include <QApplication>

int main(int argc, char *argv[])
{
    QApplication a(argc, argv);
    
    // Ensure system tray is available
    if (!QSystemTrayIcon::isSystemTrayAvailable()) {
        // Handle error or fallback
    }
    
    // Set application metadata
    a.setQuitOnLastWindowClosed(false);

    MainWindow w;
    // w.show(); // Start hidden in tray

    return a.exec();
}
