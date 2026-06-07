from eventapp.models import Event, Seat
import math

for event in Event.objects.all():
    Seat.objects.filter(event=event).delete()
    total = event.total_seats
    cols = min(10, total)
    rows_count = math.ceil(total / cols)
    event.rows = rows_count
    event.seats_per_row = cols
    event.save()
    seats_created = 0
    row_letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    for r in range(rows_count):
        row_letter = row_letters[r] if r < 26 else f'R{r+1}'
        for n in range(1, cols + 1):
            if seats_created >= total:
                break
            Seat.objects.create(
                event=event,
                row=row_letter,
                number=n,
                seat_label=f'{row_letter}{n}',
                status='available'
            )
            seats_created += 1
        if seats_created >= total:
            break
    print(f'{event.title}: {seats_created} seats created')