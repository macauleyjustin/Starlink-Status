#ifndef STARLINKCLIENT_H
#define STARLINKCLIENT_H

#include <QObject>
#include <QString>
#include <QTimer>
#include <memory>
#include <grpcpp/grpcpp.h>

// Forward declarations for generated protobuf classes
namespace SpaceX {
namespace API {
namespace Device {
class Device;
class DeviceInfo;
class Status;
class Position;
}
}
}

class StarlinkClient : public QObject
{
    Q_OBJECT

public:
    explicit StarlinkClient(const QString &target = "192.168.100.1:9200", QObject *parent = nullptr);
    ~StarlinkClient();

    void startMonitoring();
    void stopMonitoring();

signals:
    void statusChanged(bool connected);
    void speedUpdated(float downloadMbps, float uploadMbps, float latencyMs);
    void locationUpdated(double lat, double lon, double alt);
    void satelliteInfoUpdated(const QString &id, const QString &hardwareVersion);

private slots:
    void fetchStatus();

private:
    std::unique_ptr<SpaceX::API::Device::Device::Stub> stub_;
    QTimer *pollTimer_;
    QString target_;
};

#endif // STARLINKCLIENT_H
