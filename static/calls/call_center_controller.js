// This is the main controller. When a call is dequeued, we check if
// the CCO username is our username. If it is we move to the in-call view.

var CallCenterController = function($scope, $http, $location) {

    $scope.connectedEvent = function(call_str) {
        let call = JSON.parse(call_str.call);
        if (call.cco == g_username) {
            $scope.$apply(function() {
                $location.path( '/call' );
            });
        }
    }

    g_channel.bind(g_connected_event_name, $scope.connectedEvent);
}
