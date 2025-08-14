from rest_framework import serializers

class PlanTripInput(serializers.Serializer):
    current_location = serializers.CharField()
    pickup_location  = serializers.CharField()
    dropoff_location = serializers.CharField()
    current_cycle_used_hours = serializers.FloatField()
    start_time_iso = serializers.DateTimeField(required=False)
