#include "starlinkclient.h"
#include "spacex/api/device/device.grpc.pb.h"
#include "spacex/api/device/device.pb.h"
#include <grpcpp/create_channel.h>
#include <QDebug>

using grpc::Channel;
using grpc::ClientContext;
using grpc::Status;

StarlinkClient::StarlinkClient(const QString &target, QObject *parent)
    : QObject(parent), target_(target)
{
    // Create gRPC channel
    auto channel = grpc::CreateChannel(target.toStdString(), grpc::InsecureChannelCredentials());
    stub_ = SpaceX::API::Device::Device::NewStub(channel);

    pollTimer_ = new QTimer(this);
    connect(pollTimer_, &QTimer::timeout, this, &StarlinkClient::fetchStatus);
}

StarlinkClient::~StarlinkClient()
{
    stopMonitoring();
}

void StarlinkClient::startMonitoring()
{
    pollTimer_->start(5000); // Poll every 5 seconds
    fetchStatus(); // Initial fetch
}

void StarlinkClient::stopMonitoring()
{
    pollTimer_->stop();
}

void StarlinkClient::fetchStatus()
{
    // 1. Get Status
    {
        ClientContext context;
        SpaceX::API::Device::Request request;
        SpaceX::API::Device::Response response;
        
        request.mutable_get_status();

        Status status = stub_->Handle(&context, request, &response);

        if (status.ok()) {
            emit statusChanged(true);
            
            // Parse device info if available
            if (response.has_get_device_info()) {
                const auto& info = response.get_device_info().device_info();
                emit satelliteInfoUpdated(QString::fromStdString(info.id()), QString::fromStdString(info.hardware_version()));
            }
            
            // Note: Real status might be in a different message depending on the exact proto version
            // For now, we assume successful RPC means connected.
        } else {
            emit statusChanged(false);
            qWarning() << "gRPC Status Failed:" << status.error_message().c_str();
        }
    }

    // 2. Get Location
    {
        ClientContext context;
        SpaceX::API::Device::Request request;
        SpaceX::API::Device::Response response;

        request.mutable_get_location();

        Status status = stub_->Handle(&context, request, &response);

        if (status.ok() && response.has_get_location()) {
            const auto& loc = response.get_location();
            if (loc.has_lla()) {
                emit locationUpdated(loc.lla().lat(), loc.lla().lon(), loc.lla().alt());
            }
        }
    }
    
    // 3. Get History (often used for speed/throughput) or SpeedTest
    // Note: SpeedTest might be an active test. GetHistory is passive.
    // Let's try GetHistory for throughput.
    {
        ClientContext context;
        SpaceX::API::Device::Request request;
        SpaceX::API::Device::Response response;

        request.mutable_get_history();

        Status status = stub_->Handle(&context, request, &response);
        
        // Parsing history is complex, for this MVP we might just use a mock speed or 
        // look for a simpler "current throughput" field if available in Status.
        // In the mock, we will simulate this.
        
        // For now, let's emit dummy speed data if connected, to verify UI.
        // In a real app, we'd calculate this from the history ring buffer.
        if (status.ok()) {
             // Placeholder: 100 Mbps down, 20 Mbps up, 30ms latency
             emit speedUpdated(100.0f, 20.0f, 30.0f);
        }
    }
}
