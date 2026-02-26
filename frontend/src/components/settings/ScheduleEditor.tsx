'use client';
import React, { useState, useEffect, useRef } from 'react';
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import type { ScheduleSlot, ScheduleSlotName } from "@/lib/types";
import { Clock } from "lucide-react";

const DEFAULT_SCHEDULE: Record<ScheduleSlotName, ScheduleSlot> = {
  morning: { name: 'morning', start_time: '08:00', end_time: '10:00', is_enabled: true, max_pushes: 2 },
  work: { name: 'work', start_time: '10:00', end_time: '12:00', is_enabled: false, max_pushes: 0 },
  lunch: { name: 'lunch', start_time: '12:00', end_time: '14:00', is_enabled: true, max_pushes: 3 },
  evening: { name: 'evening', start_time: '18:00', end_time: '21:00', is_enabled: true, max_pushes: 5 },
  late_night: { name: 'late_night', start_time: '21:00', end_time: '23:00', is_enabled: true, max_pushes: 2 },
  weekend: { name: 'weekend', start_time: '09:00', end_time: '20:00', is_enabled: true, max_pushes: 10 },
};

export function ScheduleEditor() {
  const [schedule, setSchedule] = useState<Record<ScheduleSlotName, ScheduleSlot>>(DEFAULT_SCHEDULE);
  const [loading, setLoading] = useState(true);
  const saveTimeout = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    loadPrefs();
  }, []);

  const loadPrefs = async () => {
    try {
      const data = await apiClient.getPushPreferences(1);
      if (data.schedule) {
        setSchedule({ ...DEFAULT_SCHEDULE, ...data.schedule });
      }
    } catch {
      toast.error("Failed to load schedule");
    } finally {
      setLoading(false);
    }
  };

  const updateSchedule = (slotName: ScheduleSlotName, updates: Partial<ScheduleSlot>) => {
    const currentSlot = schedule[slotName] || DEFAULT_SCHEDULE[slotName];
    const newSchedule = {
      ...schedule,
      [slotName]: { ...currentSlot, ...updates },
    };
    setSchedule(newSchedule);

    if (saveTimeout.current) clearTimeout(saveTimeout.current);
    saveTimeout.current = setTimeout(async () => {
      try {
        await apiClient.updatePushPreferences(1, { schedule: newSchedule });
        toast.success("Schedule updated");
      } catch {
        toast.error("Failed to save schedule");
      }
    }, 800);
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div className="space-y-6" data-testid="schedule-editor">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(Object.keys(DEFAULT_SCHEDULE) as ScheduleSlotName[]).map((slotName) => {
          const slot = schedule[slotName] || DEFAULT_SCHEDULE[slotName];
          return (
            <div key={slotName} className="rounded-lg border bg-card text-card-foreground shadow-sm p-4 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-muted-foreground" />
                  <span className="font-medium capitalize">{slotName.replace('_', ' ')}</span>
                </div>
                <Switch
                  checked={slot.is_enabled}
                  onCheckedChange={(checked) => updateSchedule(slotName, { is_enabled: checked })}
                />
              </div>
              
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <Label className="text-xs text-muted-foreground">Start</Label>
                  <Input
                    type="time"
                    value={slot.start_time}
                    onChange={(e) => updateSchedule(slotName, { start_time: e.target.value })}
                    className="h-8"
                  />
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">End</Label>
                  <Input
                    type="time"
                    value={slot.end_time}
                    onChange={(e) => updateSchedule(slotName, { end_time: e.target.value })}
                    className="h-8"
                  />
                </div>
              </div>

              <div>
                <Label className="text-xs text-muted-foreground">Max Pushes</Label>
                <Input
                  type="number"
                  min={0}
                  value={slot.max_pushes}
                  onChange={(e) => updateSchedule(slotName, { max_pushes: parseInt(e.target.value) || 0 })}
                  className="h-8 mt-1"
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
