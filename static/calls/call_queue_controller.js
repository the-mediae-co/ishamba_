// A controller for the call-queue view
// We need to watch for new calls, connected calls and dequeued calls
// For now, in all events we will just reload the queue

var CallQueueController = function($scope, $http) {
    $scope.calls = [];

    $scope.reloadQueue = function() {
        // console.log("Reloading queue...");
        $http({
          method: 'get',
          url: g_call_queue_url,
          headers: {
            'Accept': 'application/json'
          }
        }).then(function(response) {
                _.each(response.data, function(call) {
                    call.since = new Date(call.created_on).getTime();
                });
                $scope.calls = response.data;
        },function(error) {
            alert("Error while trying to refresh the queue ..." + error);
        });
    }

    $scope.newCall = function() {
        $scope.reloadQueue();
        $("#new-call-sound")[0].play().catch(error => {
            // Autoplay was prevented.
            console.log(error);
        });
    }

    $scope.reloadQueue();

    g_channel.bind(g_new_call_event_name, $scope.newCall);
    g_channel.bind(g_connected_event_name, $scope.reloadQueue);
    g_channel.bind(g_hang_call_event_name, $scope.reloadQueue);

    $scope.$on('$destroy', function() {
        // We need to unbind from the events because when router navigation occurs
        // angular will create a *new* CallQueueController which will *also*
        // bind to the same events !
        g_channel.unbind(g_new_call_event_name, $scope.reloadQueue);
        g_channel.unbind(g_connected_event_name, $scope.reloadQueue);
        g_channel.unbind(g_hang_call_event_name, $scope.reloadQueue);
    });
}
