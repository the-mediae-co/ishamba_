// How pusher member subscription works:
// ------------------------------------
// When somebody joins a presence channel:
// 1. *they* receive the pusher:subscription_succeeded event with *all* the members of the channel (including themselves),
//    so they should use this to create the initial member list of that channel.
// 2. *other* users will receive a pusher:member_added event with the *new* member of that channel,
//    so they should push this user to their user list.
// 3. When a user leaves a channel (closes browser), *other* users will receive the pusher:member_removed event
//    with the *removed* member of the channel, so they need to remove the user from their user list.

var MembersController = function($scope) {
    $scope.members = [];

    g_channel.bind("pusher:subscription_succeeded", function(members) {

        //console.log("Subscription! here are the members: ");
        $scope.$apply(
            members.each(function(member) {
                //console.log(member);
                $scope.members.push(member);
            })
        );
        //console.log("And I am ... " );
        //console.log(members.me);
    });

    g_channel.bind("pusher:member_added", function(member) {
        $scope.$apply(function() {
            //console.log("A new subscription was found: ");
            //console.log(member);
            $scope.members.push(member);
        });
    });

    g_channel.bind("pusher:member_removed", function(member) {
        $scope.$apply(function() {
            $scope.members.splice($scope.members.indexOf(member), 1);
            //console.log("Somebody left: ");
            //console.log(member);
        });
    });
}
