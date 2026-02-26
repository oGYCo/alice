import { Card, CardContent, CardHeader, CardFooter } from '@/components/ui/card';

export function FeedSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <Card key={i} className="flex flex-col h-[300px] overflow-hidden animate-pulse">
          <CardHeader className="p-4 space-y-3">
            <div className="flex justify-between items-center">
              <div className="h-4 w-20 bg-muted rounded" />
              <div className="h-4 w-12 bg-muted rounded" />
            </div>
            <div className="h-6 w-3/4 bg-muted rounded" />
            <div className="h-4 w-1/2 bg-muted rounded" />
          </CardHeader>
          <CardContent className="flex-1 p-4 pt-0 space-y-2">
            <div className="h-3 w-full bg-muted rounded" />
            <div className="h-3 w-full bg-muted rounded" />
            <div className="h-3 w-2/3 bg-muted rounded" />
          </CardContent>
          <CardFooter className="p-2 border-t bg-muted/10 h-10 flex justify-between gap-2">
            <div className="h-6 w-1/4 bg-muted rounded" />
            <div className="h-6 w-1/4 bg-muted rounded" />
            <div className="h-6 w-1/4 bg-muted rounded" />
            <div className="h-6 w-1/4 bg-muted rounded" />
          </CardFooter>
        </Card>
      ))}
    </div>
  );
}
