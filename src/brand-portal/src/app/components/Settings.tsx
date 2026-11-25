import { useCallback, useEffect, useRef, useState } from "react";
import { ImagePlus } from "lucide-react";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Separator } from "./ui/separator";
import { Switch } from "./ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Textarea } from "./ui/textarea";

const initialProfile = {
  brandName: "BRAND NAME",
  description: "Российский бренд городской одежды. Минималистичный дизайн, качественные материалы.",
  email: "contact@example.invalid",
  phone: "+1 (202) 555-0102",
  site: "https://brand.example.invalid",
};

const notificationRows = [
  { id: "newOrder", label: "Новый заказ" },
  { id: "statusChange", label: "Изменение статуса" },
  { id: "payout", label: "Выплата" },
  { id: "feedSync", label: "Синхронизация фида" },
] as const;

const initialNotifications: Record<NotificationKey, boolean> = {
  newOrder: true,
  statusChange: true,
  payout: true,
  feedSync: false,
};

const initialRequisites = {
  legalEntity: 'Fictional Studio LLC',
  inn: "0000000000",
  kpp: "000000000",
  account: "00000000000000000000",
  bik: "000000000",
  corrAccount: "00000000000000000000",
  bank: "Fictional Demo Bank",
};

type Profile = typeof initialProfile;
type NotificationKey = (typeof notificationRows)[number]["id"];
type Requisites = typeof initialRequisites;

function SaveButton({ saved, onClick }: { saved: boolean; onClick: () => void }) {
  return (
    <Button onClick={onClick} variant={saved ? "secondary" : "default"}>
      {saved ? "Сохранено ✓" : "Сохранить"}
    </Button>
  );
}

export function Settings() {
  const [profile, setProfile] = useState<Profile>(initialProfile);
  const [notifications, setNotifications] = useState<Record<NotificationKey, boolean>>(initialNotifications);
  const [requisites, setRequisites] = useState<Requisites>(initialRequisites);

  const [profileSaved, setProfileSaved] = useState(false);
  const [notificationsSaved, setNotificationsSaved] = useState(false);
  const [requisitesSaved, setRequisitesSaved] = useState(false);
  const profileTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const notificationsTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const requisitesTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const saveProfile = useCallback(() => {
    setProfileSaved(true);
    if (profileTimerRef.current) clearTimeout(profileTimerRef.current);
    profileTimerRef.current = setTimeout(() => setProfileSaved(false), 2500);
  }, []);

  const saveNotifications = useCallback(() => {
    setNotificationsSaved(true);
    if (notificationsTimerRef.current) clearTimeout(notificationsTimerRef.current);
    notificationsTimerRef.current = setTimeout(() => setNotificationsSaved(false), 2500);
  }, []);

  const saveRequisites = useCallback(() => {
    setRequisitesSaved(true);
    if (requisitesTimerRef.current) clearTimeout(requisitesTimerRef.current);
    requisitesTimerRef.current = setTimeout(() => setRequisitesSaved(false), 2500);
  }, []);

  const updateProfile = useCallback(<K extends keyof Profile>(key: K, value: Profile[K]) => {
    setProfile((current) => ({ ...current, [key]: value }));
    setProfileSaved(false);
  }, []);

  const updateRequisites = useCallback(<K extends keyof Requisites>(key: K, value: Requisites[K]) => {
    setRequisites((current) => ({ ...current, [key]: value }));
    setRequisitesSaved(false);
  }, []);

  const updateNotification = useCallback((key: NotificationKey, value: boolean) => {
    setNotifications((current) => ({ ...current, [key]: value }));
    setNotificationsSaved(false);
  }, []);

  useEffect(() => {
    return () => {
      if (profileTimerRef.current) clearTimeout(profileTimerRef.current);
      if (notificationsTimerRef.current) clearTimeout(notificationsTimerRef.current);
      if (requisitesTimerRef.current) clearTimeout(requisitesTimerRef.current);
    };
  }, []);

  return (
    <section className="max-w-[980px] p-4 md:p-8">
      <div className="mb-5 md:mb-6">
        <h1 className="text-foreground">Настройки</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">Профиль, уведомления и реквизиты бренда</p>
      </div>

      <Tabs defaultValue="profile" className="gap-5">
        <TabsList className="w-full justify-start overflow-x-auto rounded-md md:w-fit">
          <TabsTrigger value="profile">Профиль бренда</TabsTrigger>
          <TabsTrigger value="notifications">Уведомления</TabsTrigger>
          <TabsTrigger value="requisites">Реквизиты</TabsTrigger>
        </TabsList>

        <TabsContent value="profile">
          <Card>
            <CardContent className="space-y-5 p-4 md:p-5">
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-muted-foreground">Логотип</Label>
                <div className="flex h-28 w-28 items-center justify-center rounded-md border border-border bg-muted hover:bg-accent">
                  <div className="text-center">
                    <ImagePlus size={20} strokeWidth={1.5} className="mx-auto mb-1 text-muted-foreground/50" />
                    <span className="text-xs text-muted-foreground">Загрузить</span>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="brandName">Название бренда</Label>
                  <Input
                    id="brandName"
                    value={profile.brandName}
                    onChange={(event) => updateProfile("brandName", event.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="profileEmail">Контактный email</Label>
                  <Input
                    id="profileEmail"
                    type="email"
                    value={profile.email}
                    onChange={(event) => updateProfile("email", event.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="profilePhone">Телефон</Label>
                  <Input
                    id="profilePhone"
                    type="tel"
                    value={profile.phone}
                    onChange={(event) => updateProfile("phone", event.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="profileSite">Сайт</Label>
                  <Input
                    id="profileSite"
                    type="url"
                    value={profile.site}
                    onChange={(event) => updateProfile("site", event.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="profileDescription">Описание</Label>
                <Textarea
                  id="profileDescription"
                  rows={4}
                  value={profile.description}
                  onChange={(event) => updateProfile("description", event.target.value)}
                />
              </div>

              <Separator />
              <div className="flex justify-end">
                <SaveButton saved={profileSaved} onClick={saveProfile} />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notifications">
          <Card>
            <CardContent className="p-0">
              <div className="grid grid-cols-[1fr_auto] border-b border-border bg-muted/50 px-4 py-3 text-xs uppercase tracking-wider text-muted-foreground">
                <span>Событие</span>
                <span>Email</span>
              </div>
              <div className="divide-y divide-border">
                {notificationRows.map((row) => (
                  <div key={row.id} className="grid grid-cols-[1fr_auto] items-center gap-4 px-4 py-4">
                    <Label htmlFor={`notification-${row.id}`} className="text-sm text-foreground">
                      {row.label}
                    </Label>
                    <Switch
                      id={`notification-${row.id}`}
                      checked={notifications[row.id]}
                      onCheckedChange={(checked) => updateNotification(row.id, checked)}
                    />
                  </div>
                ))}
              </div>
              <div className="flex justify-end border-t border-border p-4">
                <SaveButton saved={notificationsSaved} onClick={saveNotifications} />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="requisites">
          <Card>
            <CardContent className="space-y-5 p-4 md:p-5">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="legalEntity">Юр. лицо</Label>
                  <Input
                    id="legalEntity"
                    value={requisites.legalEntity}
                    onChange={(event) => updateRequisites("legalEntity", event.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="inn">ИНН</Label>
                  <Input
                    id="inn"
                    value={requisites.inn}
                    onChange={(event) => updateRequisites("inn", event.target.value)}
                    className="font-mono"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="kpp">КПП</Label>
                  <Input
                    id="kpp"
                    value={requisites.kpp}
                    onChange={(event) => updateRequisites("kpp", event.target.value)}
                    className="font-mono"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="account">Расчётный счёт</Label>
                  <Input
                    id="account"
                    value={requisites.account}
                    onChange={(event) => updateRequisites("account", event.target.value)}
                    className="font-mono"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="bik">БИК</Label>
                  <Input
                    id="bik"
                    value={requisites.bik}
                    onChange={(event) => updateRequisites("bik", event.target.value)}
                    className="font-mono"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="corrAccount">Корр. счёт</Label>
                  <Input
                    id="corrAccount"
                    value={requisites.corrAccount}
                    onChange={(event) => updateRequisites("corrAccount", event.target.value)}
                    className="font-mono"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="bank">Банк</Label>
                  <Input
                    id="bank"
                    value={requisites.bank}
                    onChange={(event) => updateRequisites("bank", event.target.value)}
                  />
                </div>
              </div>

              <Separator />
              <div className="flex justify-end">
                <SaveButton saved={requisitesSaved} onClick={saveRequisites} />
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </section>
  );
}
