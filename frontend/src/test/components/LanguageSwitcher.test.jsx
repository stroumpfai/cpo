import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from '../../components/LanguageSwitcher.jsx';
import { renderWithRouter } from '../utils.jsx';

// A probe alongside the switcher, so a test can watch the copy change rather
// than only the <select> value.
function Probe() {
  const { t } = useTranslation();
  return (
    <div>
      <LanguageSwitcher />
      <p>{t('order.pickPlate')}</p>
    </div>
  );
}

describe('LanguageSwitcher', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('offers every shipped language, each labelled in its own language', () => {
    renderWithRouter(<Probe />);

    const select = screen.getByLabelText('Language');
    expect(Array.from(select.options).map(o => o.textContent)).toEqual([
      'English', 'Deutsch', 'Français', 'Italiano',
    ]);
    expect(select).toHaveValue('en');
  });

  it('starts on the language the page is rendered in', () => {
    renderWithRouter(<Probe />, { lng: 'it-CH' });

    expect(screen.getByLabelText('Lingua')).toHaveValue('it-CH');
  });

  it('switches the visible language', async () => {
    const user = userEvent.setup();
    renderWithRouter(<Probe />);

    expect(screen.getByText('Pick a plate')).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText('Language'), 'de-CH');

    expect(await screen.findByText('Gericht auswählen')).toBeInTheDocument();
    expect(screen.getByLabelText('Sprache')).toHaveValue('de-CH');
  });

  it('remembers the choice for the next visit', async () => {
    const user = userEvent.setup();
    renderWithRouter(<Probe />);

    await user.selectOptions(screen.getByLabelText('Language'), 'fr-CH');

    expect(localStorage.getItem('cpo_lang')).toBe('fr-CH');
  });
});
