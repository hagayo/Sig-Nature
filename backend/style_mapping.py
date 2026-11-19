"""Turn artistic portrait impressions into bounded, reproducible pen rules."""
from dataclasses import dataclass

from backend.portrait_analysis import PortraitStyle


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class WritingStyle:
    """Geometry and drawing controls. All values are bounded by mapping."""
    pressure: float = 0.55       # dark/thick ink and implied paper indentation
    speed: float = 0.5           # fluidity and flourish reach
    roundness: float = 0.5       # smooth loops vs angular turns
    width: float = 1.0           # letter aspect ratio
    height: float = 1.0
    slant: float = 0.0           # horizontal displacement with vertical stroke
    irregularity: float = 0.1  # individual anchor variation
    flourish: float = 0.5      # final tail length/loop
    rise: float = 0.0          # pen direction rises on the page as RTL moves
    spacing: float = 1.0       # degree of letter compactness


def style_from_portrait(p: PortraitStyle) -> WritingStyle:
    """Combine cues, without reducing the portrait to a single emotion label."""
    return WritingStyle(
        pressure=clamp(
            0.40 + .36*p.tension + .20*p.anger + .22*p.tough
            - .18*p.softness - .12*p.calm, .18, .98,
        ),
        speed=clamp(.35 + .34*p.energy + .23*p.playful + .14*p.joy
                    - .18*p.sadness, .18, .98),
        roundness=clamp(.42 + .36*p.cute + .22*p.friendly + .20*p.softness
                        - .32*p.tough - .24*p.villainous - .15*p.anger, .08, .97),
        width=clamp(.88 + .23*p.confidence + .13*p.joy + .08*p.energy
                    - .18*p.shyness - .13*p.sadness, .72, 1.34),
        height=clamp(.86 + .18*p.confidence + .13*p.dramatic + .08*p.energy
                     - .12*p.shyness, .78, 1.28),
        slant=clamp(-.08 + .18*p.energy + .18*p.dramatic + .10*p.head_tilt
                    - .12*p.calm, -.22, .28),
        irregularity=clamp(.055 + .22*p.tension + .22*p.playful
                            + .15*p.energy - .18*p.elegance - .11*p.calm,
                            .012, .42),
        flourish=clamp(.18 + .42*p.playful + .29*p.confidence
                       + .23*p.elegance + .13*p.villainous
                       - .22*p.shyness - .16*p.sadness, .08, 1.0),
        rise=clamp(.36*p.joy + .16*p.playful - .42*p.sadness
                   - .13*p.tension, -.45, .45),
        spacing=clamp(.92 + .18*p.joy + .11*p.confidence
                      - .22*p.tension - .19*p.shyness, .68, 1.25),
    )
