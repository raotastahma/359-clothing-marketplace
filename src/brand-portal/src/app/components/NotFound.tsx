import { useNavigate } from "react-router";
import { Button } from "./ui/button";
import { Separator } from "./ui/separator";

export function NotFound() {
  const navigate = useNavigate();

  return (
    <div className="h-full flex items-center justify-center px-6">
      <div className="text-center -mt-16">
        <div
          className="text-[120px] md:text-[150px] leading-[1] tracking-tight text-muted/60 select-none pointer-events-none font-[300]"
          aria-hidden="true"
        >
          404
        </div>

        <Separator className="mt-2 mb-5" />

        <h1 className="text-[18px] md:text-[20px] text-foreground">
          Страница не найдена
        </h1>

        <p className="text-[13px] text-muted-foreground mt-3 max-w-[280px] mx-auto leading-[1.6]">
          Возможно, она была удалена или вы ввели неверный адрес
        </p>

        <Button className="mt-6" onClick={() => navigate("/")}>
          Вернуться
        </Button>
      </div>
    </div>
  );
}
