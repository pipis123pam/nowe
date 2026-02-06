import kivy
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.network.urlrequest import UrlRequest
from kivy.properties import StringProperty, NumericProperty, ObjectProperty, ListProperty
from kivy.graphics.texture import Texture
from kivy.graphics import Color, Line, Ellipse, Rectangle
from kivy.uix.popup import Popup
from kivy.clock import Clock
import json
import datetime

Window.size = (400, 800)

class AppSettings(Widget):
    font_scale = NumericProperty(1.0)
    brightness = NumericProperty(1.0) 

class Gradient(Widget):
    def vertical_gradient(self, color1, color2):
        texture = Texture.create(size=(1, 2), colorfmt='rgba')
        pixels = color2 + color1
        pixels_bytes = bytes([int(p * 255) for p in pixels])
        texture.blit_buffer(pixels_bytes, colorfmt='rgba', bufferfmt='ubyte')
        return texture

class WelcomeScreen(Screen):
    pass

class StatBox(ButtonBehavior, BoxLayout):
    title = StringProperty("")
    value = StringProperty("")
    icon_source = StringProperty("") 

class DayCard(ButtonBehavior, BoxLayout):
    temp = StringProperty("--")
    day_name = StringProperty("Dzień")
    icon_source = StringProperty("weather.png") 

    def __init__(self, day_name, day_data, controller, **kwargs):
        super().__init__(**kwargs)
        self.day_data = day_data
        self.controller = controller
        self.day_name = day_name
        
        temps = day_data.get('temperature', [])
        if temps:
            mid_idx = len(temps) // 2
            val = float(temps[mid_idx])
            self.temp = f"{val:.0f}°"
            if val > 0: self.icon_source = "brightness.png"
            else: self.icon_source = "weather.png"
        else:
            self.temp = "--"
            self.icon_source = "weather.png"

    def on_press(self):
        self.controller.open_details(self.day_name, self.day_data)

class SettingsPopup(Popup):
    app_ref = ObjectProperty(None)

class InteractiveChart(Widget):
    data_points = ListProperty([])
    mode = StringProperty('temp')
    points_coords = [] 

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cursor_label = Label(
            text="", 
            size_hint=(None, None), 
            size=(100, 40),
            color=(1, 1, 1, 1),
            bold=True
        )
        with self.cursor_label.canvas.before:
            Color(0.2, 0.2, 0.3, 0.9)
            self.bg_rect = Rectangle(size=self.cursor_label.size, pos=self.cursor_label.pos)
        
        self.cursor_label.bind(pos=self.update_label_bg, size=self.update_label_bg)

    def update_label_bg(self, *args):
        self.bg_rect.pos = self.cursor_label.pos
        self.bg_rect.size = self.cursor_label.size

    def update_chart(self, data, mode):
        self.data_points = data
        self.mode = mode
        self.canvas.after.clear()
        self.clear_widgets() 
        self.draw_base_chart()

    def draw_base_chart(self):
        if not self.data_points: return

        min_val = min(self.data_points)
        max_val = max(self.data_points)
        count = len(self.data_points)
        
        margin_x = 40
        margin_y = 50
        width = self.width - 2 * margin_x
        height = self.height - 2 * margin_y
        
        if width <= 0: return

        val_range = max_val - min_val
        if val_range == 0: val_range = 1
        
        self.points_coords = []
        line_points = []
        step_x = width / (count - 1) if count > 1 else 0

        line_color = (1, 0.8, 0.2, 1) 
        if self.mode == 'wind': line_color = (0.8, 0.8, 0.85, 1)
        if self.mode == 'rain': line_color = (0.3, 0.6, 1, 1)

        with self.canvas.after:
            Color(*line_color)
            for i, val in enumerate(self.data_points):
                x = self.x + margin_x + (i * step_x)
                normalized = (val - min_val) / val_range
                y = self.y + margin_y + (normalized * height)
                
                line_points.extend([x, y])
                self.points_coords.append((x, y, val, i))
                
                Color(1, 1, 1, 1)
                Ellipse(pos=(x-3, y-3), size=(6, 6))
                
                if i % 4 == 0: 
                    Label(text=f"{i}:00", center_x=x, y=self.y + 10, 
                          font_size=11, color=(1,1,1,0.6), 
                          size_hint=(None, None), size=(30, 20)).parent = self

            Color(*line_color)
            Line(points=line_points, width=2)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.show_cursor(touch.x)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos):
            self.show_cursor(touch.x)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        return super().on_touch_up(touch)

    def show_cursor(self, touch_x):
        if not self.points_coords: return

        closest = min(self.points_coords, key=lambda p: abs(p[0] - touch_x))
        cx, cy, val, hour = closest

        unit = "°C" if self.mode == 'temp' else (" km/h" if self.mode == 'wind' else " mm")

        self.canvas.after.remove_group('cursor')
        with self.canvas.after:
            Color(1, 1, 1, 0.5, group='cursor')
            Line(points=[cx, self.y + 30, cx, self.top - 10], width=1, group='cursor')
            Color(1, 1, 1, 1, group='cursor')
            Ellipse(pos=(cx-5, cy-5), size=(10, 10), group='cursor')

        self.cursor_label.text = f"Godz: {hour}:00\n{val:.1f}{unit}"
        
        lbl_x = cx
        if cx + 50 > self.right: lbl_x = cx - 50
        elif cx - 50 < self.x: lbl_x = cx + 50
        
        self.cursor_label.center_x = lbl_x
        self.cursor_label.y = cy + 15
        if self.cursor_label.top > self.top: self.cursor_label.top = cy - 15

        if self.cursor_label.parent != self:
            self.add_widget(self.cursor_label)

class DetailsScreen(Screen):
    day_title = StringProperty("Szczegóły")
    avg_temp = StringProperty("--")
    avg_wind = StringProperty("--")
    rain_sum = StringProperty("--")
    
    data_temps = []
    data_winds = []
    data_rains = []
    
    def display_data(self, day_name, data):
        self.day_title = day_name
        self.data_temps = [float(x) for x in data.get('temperature', [])]
        self.data_winds = [float(x) for x in data.get('wind', [])]
        self.data_rains = [float(x) for x in data.get('shower', [])]

        if self.data_temps: self.avg_temp = f"{sum(self.data_temps)/len(self.data_temps):.1f}°C"
        if self.data_winds: self.avg_wind = f"{sum(self.data_winds)/len(self.data_winds):.1f} km/h"
        if self.data_rains: self.rain_sum = f"{sum(self.data_rains):.1f} mm"

        self.show_chart('temp')

    def show_chart(self, mode):
        data_map = {
            'temp': self.data_temps,
            'wind': self.data_winds,
            'rain': self.data_rains
        }
        Clock.schedule_once(lambda dt: self.ids.chart_widget.update_chart(data_map.get(mode, []), mode), 0.1)

    def go_back(self):
        self.ids.chart_widget.canvas.after.clear()
        self.ids.chart_widget.clear_widgets()
        self.manager.current = 'weather'

class WeatherScreen(Screen):
    current_temp = StringProperty("0°")
    current_city = StringProperty("Lokalizacja")
    current_day = StringProperty("")
    current_icon_src = StringProperty("brightness.png")
    
    pending_display_name = ""

    WOJ_MAPA = {
        "dolnośląskie": "Województwo dolnośląskie",
        "kujawsko-pomorskie": "Województwo kujawsko-pomorskie",
        "lubelskie": "Lubelskie",
        "lubuskie": "województwo lubuskie",
        "łódzkie": "Województwo łódzkie",
        "małopolskie": "Województwo małopolskie",
        "mazowieckie": "Województwo mazowieckie",
        "opolskie": "Województwo opolskie",
        "podkarpackie": "województwo podkarpackie",
        "podlaskie": "Województwo podlaskie",
        "pomorskie": "Województwo pomorskie",
        "śląskie": "Województwo śląskie",
        "świętokrzyskie": "Województwo świętokrzyskie",
        "warmińsko-mazurskie": "woj. warmińsko-mazurskie",
        "wielkopolskie": "województwo wielkopolskie",
        "zachodniopomorskie": "województwo zachodniopomorskie"
    }

    def on_enter(self, *args):
        dni = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
        now = datetime.datetime.now()
        self.current_day = dni[now.weekday()]

    def show_settings(self):
        app = App.get_running_app()
        popup = SettingsPopup(app_ref=app)
        popup.open()

    def determine_search_method(self):
        query = self.ids.search_input.text.strip()
        if not query:
            self.current_city = "Wpisz nazwę!"
            return
        if ',' in query:
            self.search_manual(query)
        else:
            self.search_auto(query)

    def search_manual(self, query):
        parts = query.split(',')
        if len(parts) < 4:
            self.current_city = "Format błędny"
            return
        raw_woj = parts[0].strip()
        key_woj = raw_woj.lower().replace("województwo", "").strip()
        areaOne = self.WOJ_MAPA.get(key_woj, raw_woj)
        place = parts[3].strip()
        
        data = {"place": place, "areaOne": areaOne, "areaTwo": parts[1].strip(), "areaThree": parts[2].strip()}
        self.send_weather_request(data, place)

    def search_auto(self, query):
        self.current_city = "Szukanie..."
        data = {"areaThree": query}
        headers = {'Content-Type': 'application/json'}
        UrlRequest('http://api.e-weather.pl/weather/placesinf', req_body=json.dumps(data), req_headers=headers, on_success=self.found_location_auto, on_failure=self.failure, on_error=self.error)

    def found_location_auto(self, req, result):
        try:
            raw_data = result.get('result', {})
            list_of_places = raw_data.get('result', []) if isinstance(raw_data, dict) else raw_data
            if not list_of_places:
                self.current_city = "Nie znaleziono"
                return
            first = list_of_places[0]
            place = self.ids.search_input.text
            areaOne, areaTwo, areaThree = "", "", ""
            if isinstance(first, dict):
                place = first.get('place', place)
                areaOne = first.get('areaOne', "")
                areaTwo = first.get('areaTwo', "")
                areaThree = first.get('areaThree', "")
            elif isinstance(first, list):
                if len(first) >= 1: place = first[0]
                for item in first:
                    if isinstance(item, str) and "województwo" in item.lower():
                        areaOne = item; break
                if not areaOne and len(first) >= 2: areaOne = first[-1]
                remaining = [x for x in first if x != place and x != areaOne]
                if remaining: areaTwo, areaThree = remaining[0], remaining[0]
                else: 
                    if len(first) > 1: areaTwo, areaThree = first[1], first[1]
                    else: areaTwo, areaThree = place, place
            
            data = {"place": place, "areaOne": areaOne, "areaTwo": areaTwo, "areaThree": areaThree}
            self.send_weather_request(data, place)
        except Exception as e:
            print(e)
            self.current_city = "Błąd danych"

    def send_weather_request(self, data, display_name):
        self.pending_display_name = display_name.title()
        
        headers = {'Content-Type': 'application/json'}
        UrlRequest('http://api.e-weather.pl/weather/place', req_body=json.dumps(data), req_headers=headers, on_success=self.success_weather, on_failure=self.failure, on_error=self.error)

    def success_weather(self, req, result):
        try:
            main_result = result.get('result', {})
            forecasts = main_result.get('result', [])
            if not forecasts:
                self.current_city = "Brak danych"
                return

            today = forecasts[0]
            raw_temp = today['temperature'][0] if today['temperature'] else "0"
            temp_val = float(raw_temp)
            self.current_temp = f"{temp_val:.0f}°"
            self.current_city = self.pending_display_name
            
            if temp_val > 0: self.current_icon_src = "brightness.png"
            else: self.current_icon_src = "weather.png"

            self.ids.forecast_grid.clear_widgets()
            dni_tyg = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
            today_idx = datetime.datetime.now().weekday()

            for i, day_data in enumerate(forecasts[:7]):
                idx = (today_idx + i) % 7
                day_name = dni_tyg[idx]
                card = DayCard(day_name=day_name, day_data=day_data, controller=self)
                self.ids.forecast_grid.add_widget(card)
        except Exception as e:
            print(f"Błąd: {e}")
            self.current_city = "Błąd"

    def failure(self, req, result): self.current_city = "Błąd API"
    def error(self, req, error): self.current_city = "Błąd sieci"

    def open_details(self, day_name, data):
        details = self.manager.get_screen('details')
        details.display_data(day_name, data)
        self.manager.transition.direction = 'left'
        self.manager.current = 'details'

class WeatherApp(App):
    app_settings = ObjectProperty(None)
    def build(self):
        self.app_settings = AppSettings()
        root = FloatLayout()
        sm = ScreenManager()
        sm.add_widget(WelcomeScreen(name='welcome'))
        sm.add_widget(WeatherScreen(name='weather'))
        sm.add_widget(DetailsScreen(name='details'))
        root.add_widget(sm)
        
        self.brightness_overlay = Widget()
        self.brightness_overlay.canvas.add(Color(0, 0, 0, 0)) 
        self.brightness_overlay.rect = Rectangle(pos=root.pos, size=Window.size) 
        self.brightness_overlay.canvas.add(self.brightness_overlay.rect)
        
        Window.bind(size=self.update_overlay)
        self.app_settings.bind(brightness=self.update_brightness)
        root.add_widget(self.brightness_overlay)
        return root

    def update_overlay(self, instance, value):
        self.brightness_overlay.rect.size = value

    def update_brightness(self, instance, value):
        alpha = max(0, min(0.9, (1.0 - value)))
        self.brightness_overlay.canvas.clear()
        with self.brightness_overlay.canvas:
            Color(0, 0, 0, alpha)
            self.brightness_overlay.rect = Rectangle(pos=(0,0), size=Window.size)

if __name__ == '__main__':
    WeatherApp().run()
