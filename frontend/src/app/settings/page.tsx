import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SourceManager } from "@/components/settings/SourceManager";
import { PreferenceSliders } from "@/components/settings/PreferenceSliders";
import { ScheduleEditor } from "@/components/settings/ScheduleEditor";
import { UserModeSelector } from "@/components/settings/UserModeSelector";

export default function SettingsPage() {
  return (
    <div className="container mx-auto py-8 max-w-4xl space-y-8 px-4">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Manage your sources, preferences, and push schedule.
        </p>
      </div>

      <Tabs defaultValue="sources" className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="sources">Sources</TabsTrigger>
          <TabsTrigger value="preferences">Preferences</TabsTrigger>
          <TabsTrigger value="schedule">Schedule</TabsTrigger>
          <TabsTrigger value="profile">Profile</TabsTrigger>
        </TabsList>

        <TabsContent value="sources" className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Content Sources</h2>
            <p className="text-sm text-muted-foreground">
              Add RSS feeds or arXiv categories to track.
            </p>
            <SourceManager />
          </div>
        </TabsContent>

        <TabsContent value="preferences" className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Push Preferences</h2>
            <p className="text-sm text-muted-foreground">
              Customize how Alice filters and prioritizes content.
            </p>
            <PreferenceSliders />
          </div>
        </TabsContent>

        <TabsContent value="schedule" className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Push Schedule</h2>
            <p className="text-sm text-muted-foreground">
              Configure when you want to receive updates.
            </p>
            <ScheduleEditor />
          </div>
        </TabsContent>

        <TabsContent value="profile" className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">User Mode</h2>
            <p className="text-sm text-muted-foreground">
              Tell Alice your current focus state.
            </p>
            <UserModeSelector />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
